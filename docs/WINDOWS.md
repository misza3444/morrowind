# Windows x64

Najprostsza ścieżka to jednorazowe rozpakowanie `LowcaEcha-Launcher-Windows-x64.zip` i uruchamianie `Graj.exe`; gra i kolejne aktualizacje pobierają się automatycznie. Dostępny jest również pełny `LowcaEcha-Windows-x64.zip`. Wymagane są Windows 10/11 x64, .NET Framework 4.8 i sterownik z OpenGL 3.3 lub nowszym. Nie potrzeba Pythona, Gita ani Morrowinda. Instalację do istniejącego folderu, tryb offline i powrót do poprzedniej wersji opisuje [UPDATES.md](UPDATES.md).

ZIP-y są publikowane po udanym workflow [Validate and build Windows ZIP](https://github.com/misza3444/morrowind/actions/workflows/build.yml) w [wydaniu Windows](https://github.com/misza3444/morrowind/releases/tag/windows-latest) i jako artefakty Actions. Repozytorium musi być publiczne, aby launcher mógł pobierać aktualizacje bez logowania. Plik `.sha256` służy do porównania sumy pobranej paczki, np. `Get-FileHash .\LowcaEcha-Windows-x64.zip -Algorithm SHA256` w PowerShellu.

**Uruchamianie i zapis**

- `Graj.exe` uruchamia grę. Sterowanie jest takie jak w głównym README.
- `profile/user/saves` zawiera zapisy; F6 zapisuje, F7 wczytuje.
- `profile/settings.cfg` zawiera ustawienia obrazu i jest zachowywany między uruchomieniami.
- `profile/openmw.log` zawiera log aktualnej gry.
- `Graj.exe --test` wykonuje 12 testów gry w oddzielnym `test-profile`. Sukces to kod procesu 0 i `EH_TESTS_PASSED` w logu bez wpisów błędu. Stary log jest przenoszony do `openmw.previous.log`, żeby nie zaliczyć poprzedniego wyniku. Test ma limit 180 sekund.
- `Graj.exe --check` sprawdza przygotowanie profilu i ścieżek bez tworzenia okna gry; jest używany przez CI i nie jest testem rozgrywki.

Mały bootstrap C uruchamia aktualizator .NET z bieżącej wersji. Natywny program `Uruchom.exe` przygotowuje wspólny profil i konfigurację UTF-8 bez BOM, a następnie przekazuje silnikowi względny argument `--config`, aby uniknąć utraty polskich znaków przez Windows CRT. Uruchamia silnik z jego własnego katalogu i nie korzysta z globalnego profilu OpenMW.

**Praca nad kodem na Windows**

Zainstaluj Python 3.12+, Git z Git LFS oraz 7-Zip. Następnie w katalogu repozytorium:

```powershell
py -3.12 tools/setup.py
py -3.12 tools/run.py
py -3.12 tools/run.py --test
py -3.12 -m unittest discover -s tests -p "test_*.py" -v
```

Instalacja pobiera oficjalny instalator Windows OpenMW, sprawdza jego SHA-256 i wypakowuje zawartość przez 7-Zip. Nie uruchamia instalatora NSIS. Zawarte w nim biblioteki Visual C++ x64 są rozpakowywane bez zmiany podpisanych plików DLL i umieszczane lokalnie przy silniku. `app-local-runtime.json` zapisuje ich pochodzenie oraz sumy kontrolne. Git LFS pobiera zasoby przypięte do konkretnego commitu i sprawdza ich SHA-256.

Brak 7-Zip można uzupełnić przez `winget install --id 7zip.7zip -e` albo wskazać plik `7z.exe` parametrem `--seven-zip`. Katalogi `.runtime`, `build` i `dist` są pomijane przez Git.

**Budowanie ZIP-a**

Na Windows uruchom w x64 Developer Command Prompt programu Visual Studio z narzędziami C/C++:

```powershell
py -3.12 tools/setup.py
py -3.12 tools/package_windows.py
```

Na Linuksie potrzebne są 7-Zip, kompilator MinGW-w64 oraz Mono `mcs` z bibliotekami Forms, Web.Extensions i IO.Compression.FileSystem:

```sh
python3 tools/setup.py --platform windows
python3 tools/package_windows.py
```

Niestandardowe lokalizacje narzędzi można wskazać przez `--seven-zip` w instalatorze oraz `--compiler` i `--csharp-compiler` w pakowarce. Lokalny profil jest oddzielony od wersji w `versions/`. Zawartość dodatku jest generowana od nowa w katalogu tymczasowym; lokalne zapisy, logi, poprzednie modele robocze i dane Git nie trafiają do paczek. `version.json` rejestruje sumy wszystkich plików wersji i paczek aktualizacji.

**Zakres weryfikacji**

W obecnej maszynie sprawdzono 11 testów narzędzi na Linuksie i w windowsowym Pythonie przez Wine, regresję 12 testów na Linuksie i 12 testów silnika Windows uruchomionego przez Wine 10/Mesa. Weryfikacja wersji Windows obejmowała natywny `Graj.exe`, folder ze spacjami i literą „Ł”, renderowanie, walkę, kolizje, nagrody, restart oraz rzeczywisty zapis i wczytanie. Pełny zestaw gry przeszedł również po dołączeniu modeli świątyni, wyposażenia i tekstury podłoża; sprawdzono sumy wszystkich 941 plików ZIP-a oraz 11 plików wybranej paczki zasobów. To weryfikacja binariów Windows przez warstwę zgodności; nie jest pomiarem na komputerze Windows z docelową kartą graficzną.

Po dodaniu aktualizacji zestaw Pythona obejmuje 14 testów, a osobny zestaw aktualizatora 15 testów transakcji. Sprawdzono odtworzenie gry z rzeczywistych paczek i start przez `Graj.exe`, .NET oraz natywny program uruchamiający silnik w Wine z Wine Mono, z 12 testami rozgrywki. Mały launcher sprawdzono także na dotychczasowej płaskiej paczce, zachowując zapis i ustawienia.

Workflow Windows wykonuje testy narzędzi i aktualizatora, sprawdza wersję natywnego silnika, kompiluje przez MSVC i systemowy csc, odtwarza paczki i sprawdza generowanie profilu Unicode przez cały launcher. Nie traktuje testu `--check` jako testu renderowania; pełną regresję gry wykonuje osobne zadanie linuksowe. Publikacja kanału następuje po sukcesie obu zadań.
