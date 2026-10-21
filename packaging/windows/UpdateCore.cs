using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;

namespace EchoLauncher
{
    public sealed class PayloadFile { public string path; public string sha256; public long size; }
    public sealed class Bundle
    {
        public string name; public string id; public string asset; public string sha256;
        public long size; public PayloadFile[] files;
    }
    public sealed class Release
    {
        public int schema; public string platform; public string version; public string revision;
        public string release_tag; public Bundle[] bundles;
    }
    public interface IReleaseSource
    {
        Release Latest(CancellationToken cancel);
        void Download(Release release, Bundle bundle, string destination, Action<string> progress, CancellationToken cancel);
    }
    public sealed class AccessRequired : Exception { }

    public static class Format
    {
        public static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
        public static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 4 * 1024 * 1024 };
        public static bool Hash(string value) { return value != null && Regex.IsMatch(value, "^[0-9a-f]{64}$"); }
        public static bool Installation(string value) { return value != null && Regex.IsMatch(value, "^[0-9a-f]{32}(-[0-9a-f]{8})?$"); }
        public static string Digest(byte[] data)
        {
            using (var algorithm = SHA256.Create()) return Hex(algorithm.ComputeHash(data));
        }
        static string Hex(byte[] data) { return BitConverter.ToString(data).Replace("-", "").ToLowerInvariant(); }
        public static string FileHash(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var algorithm = SHA256.Create()) return Hex(algorithm.ComputeHash(stream));
        }
        public static string BundleId(IEnumerable<PayloadFile> files)
        {
            return Digest(Utf8.GetBytes(String.Concat(files.OrderBy(f => f.path, StringComparer.Ordinal)
                .Select(f => f.path + "\t" + f.sha256 + "\t" + f.size.ToString(CultureInfo.InvariantCulture) + "\n"))));
        }
        public static string Version(IEnumerable<Bundle> bundles)
        {
            return Digest(Utf8.GetBytes(String.Concat(bundles.OrderBy(b => b.name, StringComparer.Ordinal)
                .Select(b => b.name + "\t" + b.id + "\n"))));
        }
        public static void SafePath(string path)
        {
            if (String.IsNullOrEmpty(path) || path.Length > 220 || path.IndexOfAny(new[] { '\\', ':', '<', '>', '"', '|', '?', '*' }) >= 0 || path.Any(c => c < 32))
                throw new InvalidDataException("Niedozwolona ścieżka aktualizacji.");
            foreach (string part in path.Split('/'))
            {
                if (part.Length == 0 || part == "." || part == ".." || part.EndsWith(".") || part.EndsWith(" ") ||
                    Regex.IsMatch(part.Split('.')[0], "^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])$", RegexOptions.IgnoreCase))
                    throw new InvalidDataException("Niedozwolona nazwa pliku aktualizacji.");
            }
            if (!(path.StartsWith("engine/", StringComparison.Ordinal) || path.StartsWith("data/", StringComparison.Ordinal) ||
                path.StartsWith("config/", StringComparison.Ordinal) || path.StartsWith("licenses/", StringComparison.Ordinal) ||
                new[] { "Uruchom.exe", "Aktualizuj.exe", "Aktualizuj.exe.config", "dependencies.lock.json", "CZYTAJ.txt" }.Contains(path)))
                throw new InvalidDataException("Aktualizacja nie może zmieniać plików użytkownika.");
        }
        public static string Target(string root, string relative)
        {
            SafePath(relative);
            string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string result = Path.GetFullPath(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!result.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Ścieżka poza wersją gry.");
            return result;
        }
        public static void Validate(Release release)
        {
            if (release == null || release.schema != 1 || release.platform != "windows-x64" || !Hash(release.version) ||
                release.release_tag != "windows-" + release.version || release.bundles == null || release.bundles.Length != 2)
                throw new InvalidDataException("Nieobsługiwany opis aktualizacji.");
            var names = new HashSet<string>(StringComparer.Ordinal);
            var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            long total = 0;
            foreach (Bundle bundle in release.bundles)
            {
                if (bundle == null || !new[] { "runtime", "game" }.Contains(bundle.name) || !names.Add(bundle.name) || !Hash(bundle.id) || !Hash(bundle.sha256) ||
                    bundle.asset != bundle.name + "-" + bundle.sha256 + ".zip" || bundle.size < 1 || bundle.size > 1024L * 1024 * 1024 ||
                    bundle.files == null || bundle.files.Length == 0 || bundle.files.Length > 10000)
                    throw new InvalidDataException("Niepoprawna paczka aktualizacji.");
                foreach (PayloadFile file in bundle.files)
                {
                    if (file == null || !Hash(file.sha256) || file.size < 0 || file.size > 1024L * 1024 * 1024)
                        throw new InvalidDataException("Niepoprawny plik aktualizacji.");
                    SafePath(file.path);
                    if (!paths.Add(file.path)) throw new InvalidDataException("Powtórzona ścieżka aktualizacji.");
                    total += file.size;
                }
                if (BundleId(bundle.files) != bundle.id) throw new InvalidDataException("Niepoprawny identyfikator paczki.");
            }
            if (total > 4L * 1024 * 1024 * 1024 || Version(release.bundles) != release.version ||
                !new[] { "Uruchom.exe", "Aktualizuj.exe", "engine/openmw.exe", "config/settings.cfg", "data/template/template.omwgame", "data/game/echo.omwscripts" }.All(paths.Contains))
                throw new InvalidDataException("Niekompletna wersja gry.");
        }
    }

    public sealed class Installer
    {
        readonly string root;
        readonly Action<string> checkpoint;
        public Installer(string installRoot, Action<string> testCheckpoint = null)
        {
            root = Path.GetFullPath(installRoot);
            checkpoint = testCheckpoint ?? delegate { };
        }
        public string Current()
        {
            string pointer = Path.Combine(root, "current.txt");
            if (!File.Exists(pointer)) return null;
            string id = File.ReadAllText(pointer, Format.Utf8).Trim();
            if (!Format.Installation(id)) throw new InvalidDataException("Niepoprawny identyfikator zainstalowanej gry.");
            string version = Path.Combine(root, "versions", id);
            return Directory.Exists(version) ? version : null;
        }
        public static Release ReadVersion(string directory)
        {
            Release release = Format.Json.Deserialize<Release>(File.ReadAllText(Path.Combine(directory, "version.json"), Format.Utf8));
            Format.Validate(release);
            return release;
        }
        static bool Matches(string directory, IEnumerable<PayloadFile> files, CancellationToken cancel)
        {
            foreach (PayloadFile file in files)
            {
                cancel.ThrowIfCancellationRequested();
                string path = Format.Target(directory, file.path);
                if (!File.Exists(path) || new FileInfo(path).Length != file.size || Format.FileHash(path) != file.sha256) return false;
            }
            return true;
        }
        public static bool Complete(string directory, Release release, CancellationToken cancel)
        {
            return directory != null && Matches(directory, release.bundles.SelectMany(b => b.files), cancel);
        }
        static void CopyBundle(string source, string destination, Bundle bundle, CancellationToken cancel)
        {
            foreach (PayloadFile file in bundle.files)
            {
                cancel.ThrowIfCancellationRequested();
                string target = Format.Target(destination, file.path);
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                File.Copy(Format.Target(source, file.path), target);
            }
        }
        static void Extract(string archive, string destination, Bundle bundle, CancellationToken cancel)
        {
            var expected = bundle.files.ToDictionary(f => f.path, StringComparer.Ordinal);
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            using (var zip = ZipFile.OpenRead(archive))
            {
                foreach (ZipArchiveEntry entry in zip.Entries)
                {
                    cancel.ThrowIfCancellationRequested();
                    PayloadFile file;
                    Format.SafePath(entry.FullName);
                    if (!seen.Add(entry.FullName) || !expected.TryGetValue(entry.FullName, out file) || entry.Length != file.size ||
                        ((entry.ExternalAttributes >> 16) & 0xF000) == 0xA000)
                        throw new InvalidDataException("Nieoczekiwana zawartość ZIP-a.");
                    string target = Format.Target(destination, file.path);
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    using (var input = entry.Open())
                    using (var output = new FileStream(target, FileMode.CreateNew, FileAccess.Write))
                    {
                        byte[] buffer = new byte[65536];
                        long count = 0;
                        int received;
                        while ((received = input.Read(buffer, 0, buffer.Length)) != 0)
                        {
                            cancel.ThrowIfCancellationRequested();
                            count += received;
                            if (count > file.size) throw new InvalidDataException("Zbyt duży plik w ZIP-ie.");
                            output.Write(buffer, 0, received);
                        }
                        if (count != file.size) throw new InvalidDataException("Niepełny plik w ZIP-ie.");
                    }
                    if (Format.FileHash(target) != file.sha256) throw new InvalidDataException("Błędna suma pliku aktualizacji.");
                }
            }
            if (seen.Count != expected.Count) throw new InvalidDataException("W ZIP-ie brakuje plików.");
        }
        void Switch(string id)
        {
            if (!Format.Installation(id)) throw new InvalidDataException("Niepoprawna wersja.");
            string temporary = Path.Combine(root, ".current-" + Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    byte[] bytes = Format.Utf8.GetBytes(id + "\n");
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }
                string current = Path.Combine(root, "current.txt");
                if (File.Exists(current)) File.Replace(temporary, current, Path.Combine(root, "previous.txt"), true);
                else File.Move(temporary, current);
            }
            finally { if (File.Exists(temporary)) File.Delete(temporary); }
        }
        public string Update(IReleaseSource source, Action<string> progress, CancellationToken cancel)
        {
            progress("Sprawdzanie aktualizacji…");
            Release release = source.Latest(cancel);
            Format.Validate(release);
            string active;
            try { active = Current(); } catch (InvalidDataException) { active = null; }
            progress("Sprawdzanie plików gry…");
            Release installed = null;
            if (active != null) try { installed = ReadVersion(active); } catch { /* Rebuild damaged local metadata from the verified feed. */ }
            if (installed != null && installed.version == release.version && Complete(active, release, cancel)) return active;
            // An existing flat installation can seed the first update without re-downloading OpenMW.
            string reusable = active ?? root;
            string work = Path.Combine(root, ".update", "stage-" + Guid.NewGuid().ToString("N"));
            string stage = Path.Combine(work, "payload");
            string committed = null;
            bool published = false;
            Directory.CreateDirectory(stage);
            try
            {
                foreach (Bundle bundle in release.bundles)
                {
                    cancel.ThrowIfCancellationRequested();
                    if (Matches(reusable, bundle.files, cancel))
                    {
                        progress("Przygotowywanie zainstalowanych plików…");
                        CopyBundle(reusable, stage, bundle, cancel);
                    }
                    else
                    {
                        string archive = Path.Combine(work, bundle.asset);
                        source.Download(release, bundle, archive, progress, cancel);
                        if (new FileInfo(archive).Length != bundle.size || Format.FileHash(archive) != bundle.sha256)
                            throw new InvalidDataException("Błędna suma pobranej paczki.");
                        checkpoint("downloaded");
                        progress("Instalowanie aktualizacji…");
                        Extract(archive, stage, bundle, cancel);
                    }
                }
                if (!Complete(stage, release, cancel)) throw new InvalidDataException("Niekompletna aktualizacja.");
                File.WriteAllText(Path.Combine(stage, "version.json"), Format.Json.Serialize(release), Format.Utf8);
                checkpoint("verified");
                cancel.ThrowIfCancellationRequested();
                string id = release.version.Substring(0, 32) + "-" + Guid.NewGuid().ToString("N").Substring(0, 8);
                Directory.CreateDirectory(Path.Combine(root, "versions"));
                committed = Path.Combine(root, "versions", id);
                Directory.Move(stage, committed);
                checkpoint("before-switch");
                cancel.ThrowIfCancellationRequested();
                Switch(id);
                published = true;
                return committed;
            }
            finally
            {
                TryDelete(work);
                if (!published && committed != null) TryDelete(committed);
            }
        }
        public string Rollback()
        {
            string id = File.ReadAllText(Path.Combine(root, "previous.txt"), Format.Utf8).Trim();
            if (!Format.Installation(id)) throw new InvalidDataException("Brak poprzedniej wersji.");
            string previous = Path.Combine(root, "versions", id);
            if (!Complete(previous, ReadVersion(previous), CancellationToken.None)) throw new InvalidDataException("Poprzednia wersja jest niekompletna.");
            Switch(id);
            return previous;
        }
        public void Clean()
        {
            string active;
            try { active = Current(); } catch (InvalidDataException) { return; }
            string previous = null;
            string file = Path.Combine(root, "previous.txt");
            if (File.Exists(file))
            {
                string id = File.ReadAllText(file, Format.Utf8).Trim();
                if (Format.Installation(id)) previous = Path.Combine(root, "versions", id);
            }
            string versions = Path.Combine(root, "versions");
            if (Directory.Exists(versions)) foreach (string directory in Directory.GetDirectories(versions))
                if (Format.Installation(Path.GetFileName(directory)) && directory != active && directory != previous) TryDelete(directory);
            string updates = Path.Combine(root, ".update");
            if (Directory.Exists(updates)) foreach (string directory in Directory.GetDirectories(updates, "stage-*")) TryDelete(directory);
        }
        static void TryDelete(string directory)
        {
            try { if (Directory.Exists(directory)) Directory.Delete(directory, true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    public sealed class GitHubSource : IReleaseSource
    {
        public const string Repository = "misza3444/morrowind";
        const string Downloads = "https://github.com/" + Repository + "/releases/download";
        static bool Allowed(Uri uri)
        {
            return uri.Scheme == "https" && (uri.Host == "github.com" ||
                uri.Host == "release-assets.githubusercontent.com" || uri.Host == "github-cloud.s3.amazonaws.com" ||
                uri.Host == "github-production-release-asset-2e65be.s3.amazonaws.com");
        }
        void Fetch(string url, string accept, Stream output, long maximum, Action<long> progress, CancellationToken cancel)
        {
            Uri uri = new Uri(url);
            for (int redirect = 0; redirect < 6; ++redirect)
            {
                if (!Allowed(uri)) throw new InvalidDataException("Nieprawidłowe źródło pobierania.");
                var request = (HttpWebRequest)WebRequest.Create(uri);
                request.AllowAutoRedirect = false;
                request.Timeout = 10000;
                request.ReadWriteTimeout = 20000;
                request.UserAgent = "LowcaEcha-Launcher/1";
                request.Accept = accept;
                try
                {
                    using (cancel.Register(request.Abort))
                    using (var response = (HttpWebResponse)request.GetResponse())
                    {
                        int status = (int)response.StatusCode;
                        if (status >= 300 && status < 400)
                        {
                            uri = new Uri(uri, response.Headers["Location"]);
                            continue;
                        }
                        if (response.ContentLength > maximum) throw new InvalidDataException("Zbyt duża odpowiedź serwera.");
                        using (Stream input = response.GetResponseStream())
                        {
                            byte[] buffer = new byte[65536];
                            long count = 0;
                            int received;
                            while ((received = input.Read(buffer, 0, buffer.Length)) != 0)
                            {
                                cancel.ThrowIfCancellationRequested();
                                count += received;
                                if (count > maximum) throw new InvalidDataException("Zbyt duży pobrany plik.");
                                output.Write(buffer, 0, received);
                                progress(count);
                            }
                        }
                        return;
                    }
                }
                catch (WebException error)
                {
                    cancel.ThrowIfCancellationRequested();
                    var response = error.Response as HttpWebResponse;
                    if (response != null)
                    {
                        int status = (int)response.StatusCode;
                        response.Dispose();
                        if (status == 401 || status == 404) throw new AccessRequired();
                    }
                    throw new IOException("Nie można pobrać aktualizacji z GitHub.");
                }
            }
            throw new IOException("Zbyt wiele przekierowań pobierania.");
        }
        public Release Latest(CancellationToken cancel)
        {
            string url = Downloads + "/windows-latest/update.json";
            using (var memory = new MemoryStream())
            {
                Fetch(url, "application/octet-stream", memory, 4 * 1024 * 1024, delegate { }, cancel);
                return Format.Json.Deserialize<Release>(Format.Utf8.GetString(memory.ToArray()));
            }
        }
        public void Download(Release release, Bundle bundle, string destination, Action<string> progress, CancellationToken cancel)
        {
            string url = Downloads + "/" + Uri.EscapeDataString(release.release_tag) + "/" + Uri.EscapeDataString(bundle.asset);
            using (var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write))
                Fetch(url, "application/octet-stream", output, bundle.size, count => progress(String.Format(CultureInfo.InvariantCulture,
                    "Pobieranie aktualizacji: {0:0.0} / {1:0.0} MB", count / 1048576.0, bundle.size / 1048576.0)), cancel);
        }
    }
}
