/* Stable entry point. All updatable executables live in version directories. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>
#include <stdio.h>
#define CAPACITY 32768

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show)
{
    wchar_t *root = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, CAPACITY * sizeof(wchar_t));
    wchar_t *filename = HeapAlloc(GetProcessHeap(), 0, CAPACITY * sizeof(wchar_t));
    wchar_t *arguments = HeapAlloc(GetProcessHeap(), 0, CAPACITY * 4 * sizeof(wchar_t));
    wchar_t version[80], *separator;
    char data[80];
    DWORD length, received, code = 1;
    HANDLE file;
    size_t i;
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process;
    (void)instance; (void)previous; (void)show;
    startup.cb = sizeof(startup);
    if (!root || !filename || !arguments) goto finish;
    length = GetModuleFileNameW(NULL, root, CAPACITY);
    if (!length || length >= CAPACITY || !(separator = wcsrchr(root, L'\\'))) goto finish;
    *separator = 0;
    swprintf(filename, CAPACITY, L"%ls\\current.txt", root);
    file = CreateFileW(filename, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
    version[0] = 0;
    if (file != INVALID_HANDLE_VALUE) {
        if (ReadFile(file, data, sizeof(data), &received, NULL) && received < sizeof(data)) {
            while (received && (data[received - 1] == '\n' || data[received - 1] == '\r')) --received;
            if (received == 32 || (received == 41 && data[32] == '-')) {
                for (i = 0; i < received; ++i) {
                    if (i == 32 && received == 41) { version[i] = L'-'; continue; }
                    if (!((data[i] >= '0' && data[i] <= '9') || (data[i] >= 'a' && data[i] <= 'f'))) break;
                    version[i] = (wchar_t)data[i];
                }
                version[i == received ? received : 0] = 0;
            }
        }
        CloseHandle(file);
    }
    if (version[0]) swprintf(filename, CAPACITY, L"%ls\\versions\\%ls\\Aktualizuj.exe", root, version);
    if (!version[0] || GetFileAttributesW(filename) == INVALID_FILE_ATTRIBUTES)
        swprintf(filename, CAPACITY, L"%ls\\bootstrap\\Aktualizuj.exe", root);
    if (GetFileAttributesW(filename) == INVALID_FILE_ATTRIBUTES) goto finish;
    swprintf(arguments, CAPACITY * 4, L"\"%ls\" --root \"%ls\" %ls", filename, root, command);
    if (!CreateProcessW(filename, arguments, NULL, NULL, FALSE, 0, NULL, root, &startup, &process)) goto finish;
    WaitForSingleObject(process.hProcess, INFINITE);
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
finish:
    if (code && (!command || (!wcsstr(command, L"--check") && !wcsstr(command, L"--test"))))
        MessageBoxW(NULL, L"Nie można uruchomić gry lub aktualizatora. Rozpakuj cały pakiet launchera. Wymagany jest .NET Framework 4.8, wbudowany w nowszy Windows 10 i Windows 11.", L"Łowca Echa", MB_ICONERROR | MB_OK);
    if (root) HeapFree(GetProcessHeap(), 0, root);
    if (filename) HeapFree(GetProcessHeap(), 0, filename);
    if (arguments) HeapFree(GetProcessHeap(), 0, arguments);
    return (int)code;
}
