/* Native UTF-16 Windows launcher: independent profile, UTF-8 config, no Python. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
#include <stdio.h>
#include <string.h>

#define CAPACITY 32768

static int path(wchar_t *output, const wchar_t *root, const wchar_t *tail)
{
    if (wcslen(root) + wcslen(tail) >= CAPACITY) return 0;
    wcscpy(output, root);
    wcscat(output, tail);
    return 1;
}

static int directory(const wchar_t *name)
{
    if (CreateDirectoryW(name, NULL)) return 1;
    return GetLastError() == ERROR_ALREADY_EXISTS &&
        (GetFileAttributesW(name) & FILE_ATTRIBUTE_DIRECTORY);
}

static int utf8(HANDLE file, const wchar_t *text)
{
    DWORD written = 0;
    int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, -1, NULL, 0, NULL, NULL);
    char *buffer;
    int result;
    if (!length) return 0;
    buffer = (char *)HeapAlloc(GetProcessHeap(), 0, length);
    if (!buffer) return 0;
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text, -1, buffer, length, NULL, NULL);
    result = WriteFile(file, buffer, length - 1, &written, NULL) && written == (DWORD)(length - 1);
    HeapFree(GetProcessHeap(), 0, buffer);
    return result;
}

static int config_path(HANDLE file, const wchar_t *key, const wchar_t *value)
{
    wchar_t *copy = (wchar_t *)HeapAlloc(GetProcessHeap(), 0, (wcslen(value) + 1) * sizeof(wchar_t));
    size_t i;
    int result;
    if (!copy) return 0;
    wcscpy(copy, value);
    for (i = 0; copy[i]; ++i) if (copy[i] == L'\\') copy[i] = L'/';
    result = utf8(file, key) && utf8(file, L"=\"") && utf8(file, copy) && utf8(file, L"\"\n");
    HeapFree(GetProcessHeap(), 0, copy);
    return result;
}

static int tests_passed(const wchar_t *log)
{
    HANDLE file = CreateFileW(log, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    LARGE_INTEGER length;
    DWORD received;
    char *text;
    int result = 0;
    if (file == INVALID_HANDLE_VALUE) return 0;
    if (!GetFileSizeEx(file, &length) || length.QuadPart < 1 || length.QuadPart > 16 * 1024 * 1024) {
        CloseHandle(file);
        return 0;
    }
    text = (char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)length.QuadPart + 1);
    if (text && ReadFile(file, text, (DWORD)length.QuadPart, &received, NULL) && received == length.QuadPart) {
        text[received] = 0;
        result = strstr(text, "EH_TESTS_PASSED") != NULL && strstr(text, "EH_TESTS_FAILED") == NULL && strstr(text, " E]") == NULL;
    }
    if (text) HeapFree(GetProcessHeap(), 0, text);
    CloseHandle(file);
    return result;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show)
{
    wchar_t *root = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * sizeof(wchar_t));
    wchar_t *installation = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * sizeof(wchar_t));
    wchar_t *profile = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * sizeof(wchar_t));
    wchar_t *filename = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * sizeof(wchar_t));
    wchar_t *engine = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * sizeof(wchar_t));
    wchar_t *executable = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * sizeof(wchar_t));
    wchar_t *arguments = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * 3 * sizeof(wchar_t));
    wchar_t *separator;
    const wchar_t *error = L"Nie można przygotować profilu gry. Rozpakuj ZIP do folderu, w którym możesz zapisywać pliki.";
    HANDLE config = INVALID_HANDLE_VALUE;
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process;
    DWORD exit_code = 1, length, waited;
    int count, i, test = 0, check = 0, legacy = 0, result = 1;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &count);
    startup.cb = sizeof(startup);
    (void)instance; (void)previous; (void)command; (void)show;
    if (argv) for (i = 1; i < count; ++i) {
        if (!wcscmp(argv[i], L"--test")) test = 1;
        if (!wcscmp(argv[i], L"--check")) check = 1;
        if (!wcscmp(argv[i], L"--legacy")) legacy = 1;
    }
    if (argv) LocalFree(argv);
    if (!root || !installation || !profile || !filename || !engine || !executable || !arguments) goto finish;
    length = GetModuleFileNameW(NULL, root, CAPACITY);
    if (!length || length >= CAPACITY || !(separator = wcsrchr(root, L'\\'))) goto finish;
    separator[1] = 0;
    if (legacy) {
        if (!path(arguments, root, L"..\\")) goto finish;
        length = GetFullPathNameW(arguments, CAPACITY, root, NULL);
        if (!length || length >= CAPACITY) goto finish;
        wcscpy(installation, root);
    } else {
        if (!path(arguments, root, L"..\\..\\")) goto finish;
        length = GetFullPathNameW(arguments, CAPACITY, installation, NULL);
        if (!length || length >= CAPACITY) goto finish;
    }
    if (!path(engine, root, L"engine") || !path(executable, root, L"engine\\openmw.exe")) goto finish;
    if (GetFileAttributesW(executable) == INVALID_FILE_ATTRIBUTES) {
        error = L"Brakuje engine\\openmw.exe. Rozpakuj cały ZIP przed uruchomieniem gry.";
        goto finish;
    }
    if (!path(profile, installation, test ? L"test-profile" : L"profile") || !directory(profile)) goto finish;
    if (!path(filename, profile, L"\\user") || !directory(filename)) goto finish;
    if (!path(filename, profile, L"\\user\\data") || !directory(filename)) goto finish;
    if (!path(filename, profile, L"\\openmw.cfg")) goto finish;
    config = CreateFileW(filename, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (config == INVALID_HANDLE_VALUE) goto finish;
    if (!utf8(config, L"replace=config\nreplace=data\nreplace=content\nreplace=fallback-archive\n")) goto finish;
    if (!path(filename, profile, L"\\user") || !config_path(config, L"user-data", filename)) goto finish;
    if (!path(filename, profile, L"\\user\\data") || !config_path(config, L"data-local", filename)) goto finish;
    if (!path(filename, root, L"data\\template") || !config_path(config, L"data", filename)) goto finish;
    if (!path(filename, root, L"data\\creatures") || !config_path(config, L"data", filename)) goto finish;
    if (!path(filename, root, L"data\\echo") || !config_path(config, L"data", filename)) goto finish;
    if (!path(filename, root, L"data\\game") || !config_path(config, L"data", filename)) goto finish;
    if (!utf8(config, L"content=template.omwgame\ncontent=echo.omwaddon\ncontent=echo.omwscripts\nstart=Echo Arena\nskip-menu=1\nnew-game=0\n")) goto finish;
    if (test) {
        if (!path(filename, root, L"data\\tests") || !config_path(config, L"data", filename)) goto finish;
        if (!utf8(config, L"content=echo-tests.omwscripts\nno-sound=1\n")) goto finish;
    }
    CloseHandle(config);
    config = INVALID_HANDLE_VALUE;
    if (!path(filename, profile, L"\\settings.cfg")) goto finish;
    if (GetFileAttributesW(filename) == INVALID_FILE_ATTRIBUTES) {
        if (!path(arguments, root, L"config\\settings.cfg") || !CopyFileW(arguments, filename, TRUE)) goto finish;
    }
    if (test) {
        if (!path(filename, profile, L"\\openmw.log") || !path(arguments, profile, L"\\openmw.previous.log")) goto finish;
        if (GetFileAttributesW(filename) != INVALID_FILE_ATTRIBUTES &&
            !MoveFileExW(filename, arguments, MOVEFILE_REPLACE_EXISTING)) goto finish;
    }
    if (check) { result = 0; goto finish; }
    /* OpenMW's Windows CRT argv uses the active ANSI code page. Keep option
       arguments relative/ASCII; the Unicode working directory uses Win32W. */
    swprintf(arguments, CAPACITY * 3, L"\"%ls\" --config \"%ls%ls\" --no-grab", executable,
             legacy ? L"..\\" : L"..\\..\\..\\", test ? L"test-profile" : L"profile");
    error = L"Nie można uruchomić OpenMW. Jeżeli brakuje VCRUNTIME lub MSVCP, uruchom engine\\redist\\vc_redist.x64.exe.";
    if (!CreateProcessW(executable, arguments, NULL, NULL, FALSE, 0, NULL, engine, &startup, &process)) goto finish;
    waited = WaitForSingleObject(process.hProcess, test ? 180000 : INFINITE);
    if (waited != WAIT_OBJECT_0) {
        TerminateProcess(process.hProcess, 2);
        WaitForSingleObject(process.hProcess, 5000);
        exit_code = 2;
    } else GetExitCodeProcess(process.hProcess, &exit_code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    result = (int)exit_code;
    if (!result && test) {
        if (!path(filename, profile, L"\\openmw.log") || !tests_passed(filename)) result = 1;
    }
finish:
    if (config != INVALID_HANDLE_VALUE) CloseHandle(config);
    if (result && !test && !check) MessageBoxW(NULL, error, L"Łowca Echa", MB_ICONERROR | MB_OK);
    if (root) HeapFree(GetProcessHeap(), 0, root);
    if (installation) HeapFree(GetProcessHeap(), 0, installation);
    if (profile) HeapFree(GetProcessHeap(), 0, profile);
    if (filename) HeapFree(GetProcessHeap(), 0, filename);
    if (engine) HeapFree(GetProcessHeap(), 0, engine);
    if (executable) HeapFree(GetProcessHeap(), 0, executable);
    if (arguments) HeapFree(GetProcessHeap(), 0, arguments);
    return result;
}
