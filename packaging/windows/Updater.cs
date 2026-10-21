using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace EchoLauncher
{
    sealed class LauncherForm : Form
    {
        readonly string root;
        readonly Installer installer;
        readonly Label status;
        readonly ProgressBar bar;
        readonly Button offline, retry;
        CancellationTokenSource cancellation;
        bool busy, playOffline, playing;
        public int ExitCode { get; private set; }
        public LauncherForm(string installRoot)
        {
            root = installRoot;
            installer = new Installer(root);
            Text = "Łowca Echa";
            ClientSize = new Size(510, 205);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Segoe UI", 10);
            Controls.Add(new Label { Left = 22, Top = 18, Width = 465, Height = 35, Font = new Font("Segoe UI", 17, FontStyle.Bold), Text = "Łowca Echa" });
            status = new Label { Left = 22, Top = 65, Width = 465, Height = 46, Text = "Sprawdzanie aktualizacji…" };
            bar = new ProgressBar { Left = 22, Top = 116, Width = 465, Height = 15, Style = ProgressBarStyle.Marquee };
            offline = new Button { Left = 290, Top = 153, Width = 197, Height = 30, Text = "Graj bez aktualizacji" };
            retry = new Button { Left = 22, Top = 153, Width = 225, Height = 30, Text = "Sprawdź ponownie", Enabled = false };
            offline.Click += async delegate
            {
                playOffline = true;
                if (busy) cancellation.Cancel(); else await StartGame();
            };
            retry.Click += async delegate { await UpdateGame(); };
            FormClosing += delegate { if (cancellation != null) cancellation.Cancel(); };
            Controls.AddRange(new Control[] { status, bar, offline, retry });
            Shown += async delegate { await UpdateGame(); };
        }
        async Task UpdateGame()
        {
            busy = true;
            playOffline = false;
            retry.Enabled = false;
            bar.Style = ProgressBarStyle.Marquee;
            cancellation = new CancellationTokenSource();
            var progress = new Progress<string>(message => { if (!IsDisposed) status.Text = message; });
            bool start = false;
            try
            {
                await Task.Run(() => installer.Update(new GitHubSource(), message => ((IProgress<string>)progress).Report(message), cancellation.Token));
                start = true;
            }
            catch (AccessRequired)
            {
                status.Text = "Brak dostępnej publicznej aktualizacji. Możesz zagrać w zainstalowaną wersję bez aktualizacji.";
            }
            catch (OperationCanceledException) { start = playOffline; }
            catch
            {
                status.Text = "Nie udało się pobrać aktualizacji. Uruchamiam zainstalowaną wersję.";
                start = true;
            }
            finally { busy = false; retry.Enabled = true; bar.Style = ProgressBarStyle.Blocks; }
            if (start && !IsDisposed) await StartGame();
        }
        async Task StartGame()
        {
            if (playing) return;
            playing = true;
            offline.Enabled = retry.Enabled = false;
            try
            {
                var process = Program.Game(root, null);
                Hide();
                await Task.Run(() => process.WaitForExit());
                ExitCode = process.ExitCode;
                process.Dispose();
                Close();
            }
            catch
            {
                playing = false;
                offline.Enabled = true;
                Show();
                status.Text = "Brak kompletnej zainstalowanej gry. Sprawdź połączenie i spróbuj ponownie.";
                retry.Enabled = true;
            }
        }
    }
    public static class Program
    {
        public static Process Game(string root, string option)
        {
            string active = new Installer(root).Current();
            bool legacy = active == null;
            string executable = legacy ? Path.Combine(root, "bootstrap", "Uruchom.exe") : Path.Combine(active, "Uruchom.exe");
            if (!File.Exists(Path.Combine(active ?? root, "engine", "openmw.exe"))) throw new FileNotFoundException();
            return Process.Start(new ProcessStartInfo(executable, (legacy ? "--legacy " : "") + (option ?? ""))
                { UseShellExecute = false, WorkingDirectory = active ?? root });
        }
        [STAThread]
        public static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
            string root = null;
            for (int i = 0; i + 1 < args.Length; ++i) if (args[i] == "--root") root = Path.GetFullPath(args[++i]);
            if (root == null || !Directory.Exists(root)) return 1;
            try
            {
                using (var installLock = new FileStream(Path.Combine(root, "launcher.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None))
                {
                    var installer = new Installer(root);
                    installer.Clean();
                    string option = args.Contains("--test") ? "--test" : args.Contains("--check") ? "--check" : null;
                    if (args.Contains("--rollback")) installer.Rollback();
                    if (option != null || args.Contains("--offline") || args.Contains("--rollback"))
                    {
                        using (Process game = Game(root, option)) { game.WaitForExit(); return game.ExitCode; }
                    }
                    using (var window = new LauncherForm(root)) { Application.Run(window); return window.ExitCode; }
                }
            }
            catch
            {
                if (!args.Contains("--test") && !args.Contains("--check"))
                    MessageBox.Show("Nie można otworzyć gry. Sprawdź, czy gra jest już uruchomiona i czy możesz zapisywać pliki w jej folderze.", "Łowca Echa");
                return 1;
            }
        }
    }
}
