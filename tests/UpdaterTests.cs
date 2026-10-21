using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Threading;
using EchoLauncher;

public static class UpdaterTests
{
    sealed class PublishedSource : IReleaseSource
    {
        readonly string root;
        public int downloads;
        public PublishedSource(string directory) { root = directory; }
        public Release Latest(CancellationToken cancel)
        {
            return Format.Json.Deserialize<Release>(File.ReadAllText(Path.Combine(root, "update.json"), Format.Utf8));
        }
        public void Download(Release release, Bundle bundle, string target, Action<string> progress, CancellationToken cancel)
        {
            ++downloads;
            File.Copy(Path.Combine(root, bundle.asset), target);
        }
    }
    sealed class Source : IReleaseSource
    {
        public Release release;
        public Dictionary<string, byte[]> zips = new Dictionary<string, byte[]>();
        public Dictionary<string, byte[]> bytes = new Dictionary<string, byte[]>();
        public List<string> downloaded = new List<string>();
        public bool corrupt;
        public Release Latest(CancellationToken cancel) { cancel.ThrowIfCancellationRequested(); return release; }
        public void Download(Release r, Bundle bundle, string target, Action<string> progress, CancellationToken cancel)
        {
            downloaded.Add(bundle.name);
            byte[] data = (byte[])zips[bundle.asset].Clone();
            if (corrupt) data[data.Length / 2] ^= 1;
            File.WriteAllBytes(target, data);
        }
        public void Repack(Bundle bundle, Dictionary<string, byte[]> files)
        {
            byte[] zip;
            using (var memory = new MemoryStream())
            {
                using (var archive = new ZipArchive(memory, ZipArchiveMode.Create, true))
                    foreach (var item in files)
                        using (var stream = archive.CreateEntry(item.Key).Open()) stream.Write(item.Value, 0, item.Value.Length);
                zip = memory.ToArray();
            }
            bundle.sha256 = Format.Digest(zip);
            bundle.asset = bundle.name + "-" + bundle.sha256 + ".zip";
            bundle.size = zip.Length;
            zips[bundle.asset] = zip;
        }
    }
    sealed class Fixture : IDisposable
    {
        public string root = Path.Combine(Path.GetTempPath(), "Łowca Echa tests " + Guid.NewGuid().ToString("N"));
        public Installer installer;
        public Fixture()
        {
            Directory.CreateDirectory(Path.Combine(root, "profile", "user", "saves"));
            File.WriteAllText(Path.Combine(root, "profile", "user", "saves", "moja.omwsave"), "SAVE SENTINEL");
            File.WriteAllText(Path.Combine(root, "profile", "settings.cfg"), "MY SETTINGS");
            installer = new Installer(root);
        }
        public string Update(Source source) { return installer.Update(source, delegate { }, CancellationToken.None); }
        public void Preserved()
        {
            Check(File.ReadAllText(Path.Combine(root, "profile", "user", "saves", "moja.omwsave")) == "SAVE SENTINEL", "Save changed");
            Check(File.ReadAllText(Path.Combine(root, "profile", "settings.cfg")) == "MY SETTINGS", "Settings changed");
        }
        public void Dispose() { Directory.Delete(root, true); }
    }
    static void Check(bool value, string text) { if (!value) throw new Exception(text); }
    static void Reject(Action action)
    {
        bool failed = false;
        try { action(); } catch (Exception) { failed = true; }
        Check(failed, "Invalid update was accepted");
    }
    static Source Make(string content)
    {
        var source = new Source();
        source.bytes = new Dictionary<string, byte[]> {
            { "engine/openmw.exe", Encoding.UTF8.GetBytes("same engine") },
            { "data/template/template.omwgame", Encoding.UTF8.GetBytes("same template") },
            { "data/creatures/creature.dae", Encoding.UTF8.GetBytes("same creature") },
            { "Uruchom.exe", Encoding.UTF8.GetBytes("runner") },
            { "Aktualizuj.exe", Encoding.UTF8.GetBytes("updater") },
            { "config/settings.cfg", Encoding.UTF8.GetBytes("factory settings") },
            { "data/game/echo.omwscripts", Encoding.UTF8.GetBytes(content) }
        };
        var bundles = new List<Bundle>();
        foreach (string name in new[] { "runtime", "game" })
        {
            var selected = source.bytes.Where(item => (item.Key.StartsWith("engine/") || item.Key.StartsWith("data/template/") || item.Key.StartsWith("data/creatures/")) == (name == "runtime")).ToDictionary(i => i.Key, i => i.Value);
            var files = selected.Select(item => new PayloadFile { path = item.Key, size = item.Value.Length, sha256 = Format.Digest(item.Value) }).ToArray();
            string id = Format.BundleId(files);
            var bundle = new Bundle { name = name, id = id, asset = name + "-" + id + ".zip", files = files };
            source.Repack(bundle, selected);
            bundles.Add(bundle);
        }
        string version = Format.Version(bundles);
        source.release = new Release { schema = 1, platform = "windows-x64", version = version, revision = "test", release_tag = "windows-" + version, bundles = bundles.ToArray() };
        return source;
    }
    static Dictionary<string, byte[]> GameFiles(Source source)
    {
        return source.release.bundles.Single(b => b.name == "game").files.ToDictionary(f => f.path, f => source.bytes[f.path]);
    }
    static void Unchanged(Fixture f, string current)
    {
        Check(f.installer.Current() == current, "Live version changed after failed update");
        Check(Installer.Complete(current, Installer.ReadVersion(current), CancellationToken.None), "Installed files were damaged");
        f.Preserved();
        string staging = Path.Combine(f.root, ".update");
        Check(!Directory.Exists(staging) || Directory.GetDirectories(staging).Length == 0, "Staging left after failure");
    }
    static void Install()
    {
        using (var f = new Fixture())
        {
            var source = Make("version one");
            string active = f.Update(source);
            Check(source.downloaded.Count == 2, "First install must download both bundles");
            Check(Installer.Complete(active, source.release, CancellationToken.None), "Incomplete install");
            f.Preserved();
        }
    }
    static void Incremental()
    {
        using (var f = new Fixture())
        {
            string old = f.Update(Make("old"));
            var source = Make("new");
            string next = f.Update(source);
            Check(next != old && source.downloaded.SequenceEqual(new[] { "game" }), "Unchanged runtime downloaded again");
            Check(Installer.Complete(old, Installer.ReadVersion(old), CancellationToken.None), "Previous version removed");
            f.Preserved();
        }
    }
    static void NoUpdate()
    {
        using (var f = new Fixture())
        {
            var source = Make("same");
            string active = f.Update(source);
            source.downloaded.Clear();
            Check(f.Update(source) == active && source.downloaded.Count == 0, "Unchanged version was downloaded");
        }
    }
    static void Corrupt()
    {
        using (var f = new Fixture())
        {
            string old = f.Update(Make("old"));
            var source = Make("new"); source.corrupt = true;
            Reject(() => f.Update(source));
            Unchanged(f, old);
        }
    }
    static void InvalidZip(string mode)
    {
        using (var f = new Fixture())
        {
            string old = f.Update(Make("old"));
            var source = Make("new");
            var files = GameFiles(source);
            if (mode == "slip") files.Add("../profile/evil.txt", new byte[] { 1 });
            if (mode == "case") files.Add("CONFIG/settings.cfg", Encoding.UTF8.GetBytes("collision"));
            if (mode == "missing") files.Remove("Uruchom.exe");
            if (mode == "hash") files["Uruchom.exe"] = Encoding.UTF8.GetBytes("edited");
            source.Repack(source.release.bundles.Single(b => b.name == "game"), files);
            Reject(() => f.Update(source));
            Unchanged(f, old);
            Check(!File.Exists(Path.Combine(f.root, "profile", "evil.txt")), "ZIP escaped its staging directory");
        }
    }
    static void Cancel()
    {
        using (var f = new Fixture())
        using (var cancellation = new CancellationTokenSource())
        {
            string old = f.Update(Make("old"));
            var installer = new Installer(f.root, step => { if (step == "downloaded") cancellation.Cancel(); });
            Reject(() => installer.Update(Make("new"), delegate { }, cancellation.Token));
            Unchanged(f, old);
        }
    }
    static void InterruptedPromotion()
    {
        using (var f = new Fixture())
        {
            string old = f.Update(Make("old"));
            var installer = new Installer(f.root, step => { if (step == "before-switch") throw new IOException("simulated crash"); });
            Reject(() => installer.Update(Make("new"), delegate { }, CancellationToken.None));
            Unchanged(f, old);
        }
    }
    static void Rollback()
    {
        using (var f = new Fixture())
        {
            string old = f.Update(Make("old"));
            string next = f.Update(Make("new"));
            Check(f.installer.Rollback() == old && f.installer.Current() == old, "Rollback failed");
            Check(f.installer.Rollback() == next, "Rollback pointer was not swapped");
            f.Preserved();
        }
    }
    static void Repair()
    {
        using (var f = new Fixture())
        {
            var first = Make("same");
            string old = f.Update(first);
            File.WriteAllText(Path.Combine(old, "engine", "openmw.exe"), "corrupt");
            var source = Make("same");
            string repaired = f.Update(source);
            Check(repaired != old && source.downloaded.SequenceEqual(new[] { "runtime" }), "Same-version repair failed");
            Check(Installer.Complete(repaired, source.release, CancellationToken.None), "Repair incomplete");
        }
    }
    static void Paths()
    {
        foreach (string path in new[] { "../profile/saves", "profile/settings.cfg", "/engine/file", "engine/../../outside", "engine\\bad", "engine/file:stream", "engine/NUL.txt", "engine/a.", "engine/a ", "engine//a" })
            Reject(() => Format.SafePath(path));
        var source = Make("valid");
        source.release.schema = 99;
        Reject(() => Format.Validate(source.release));
    }
    static void RepairMetadata()
    {
        foreach (string target in new[] { "version.json", "current.txt" }) using (var f = new Fixture())
        {
            var source = Make("same");
            string old = f.Update(source);
            File.WriteAllText(target == "version.json" ? Path.Combine(old, target) : Path.Combine(f.root, target), "damaged metadata");
            f.installer.Clean();
            string repaired = f.Update(source);
            Check(repaired != old && Installer.Complete(repaired, source.release, CancellationToken.None), "Damaged metadata was not repaired");
            f.Preserved();
        }
    }
    static void LegacySeed()
    {
        using (var f = new Fixture())
        {
            var source = Make("new");
            foreach (var pair in source.bytes.Where(i => i.Key.StartsWith("engine/") || i.Key.StartsWith("data/template/") || i.Key.StartsWith("data/creatures/")))
            {
                string target = Format.Target(f.root, pair.Key);
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                File.WriteAllBytes(target, pair.Value);
            }
            f.Update(source);
            Check(source.downloaded.SequenceEqual(new[] { "game" }), "Legacy runtime was downloaded again");
            f.Preserved();
        }
    }
    public static int Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--feed-dir")
        {
            using (var fixture = new Fixture())
            {
                var source = new PublishedSource(args[1]);
                string active = fixture.installer.Update(source, delegate { }, CancellationToken.None);
                Check(Installer.Complete(active, source.Latest(CancellationToken.None), CancellationToken.None), "Published package is incomplete");
                Check(source.downloads == 2, "Published bundles not reconstructed");
                fixture.installer.Update(source, delegate { }, CancellationToken.None);
                Check(source.downloads == 2, "Reconstructed package downloaded again");
                fixture.Preserved();
                Console.WriteLine("PUBLISHED_UPDATE_TEST_PASSED");
                return 0;
            }
        }
        Action[] tests = { Install, Incremental, NoUpdate, Corrupt, () => InvalidZip("slip"), () => InvalidZip("case"),
            () => InvalidZip("missing"), () => InvalidZip("hash"), Cancel, InterruptedPromotion, Rollback, Repair, RepairMetadata, Paths, LegacySeed };
        try
        {
            for (int i = 0; i < tests.Length; ++i) { tests[i](); Console.WriteLine("UPDATER_PASS " + (i + 1)); }
            Console.WriteLine("UPDATER_TESTS_PASSED: " + tests.Length);
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
}
