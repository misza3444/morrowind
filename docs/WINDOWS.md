# Windows x64

Najprostsza ścieżka to rozpakowanie `LowcaEcha-Windows-x64.zip` i uruchomienie `Graj.exe`. Pliki silnika, zasoby i biblioteki Visual C++ są w paczce. Nie potrzeba Pythona, Gita, Morrowinda ani instalacji gry w systemie. Wymagany jest Windows 10/11 x64 i sterownik z OpenGL 3.3 lub nowszym.

ZIP jest wynikiem workflow [Validate and build Windows ZIP](https://github.com/misza3444/morrowind/actions/workflows/build.yml). Otwórz udany przebieg, pobierz artefakt `LowcaEcha-Windows-x64`, a następnie rozpakuj zawarty w nim ZIP gry. Plik `.sha256` służy do porównania sumy pobranej paczki, np. `Get-FileHash .\LowcaEcha-Windows-x64.zip -Algorithm SHA256` w PowerShellu.

**Uruchamianie i zapis**

- `Graj.exe` uruchamia grę. Sterowanie jest takie jak w głównym README.
- `profile/user/saves` zawiera zapisy; F6 zapisuje, F7 wczytuje.
- `profile/settings.cfg` zawiera ustawienia obrazu i jest zachowywany między uruchomieniami.
- `profile/openmw.log` zawiera log aktualnej gry.
- `Graj.exe --test` wykonuje 12 testów gry w oddzielnym `test-profile`. Sukces to kod procesu 0 i `EH_TESTS_PASSED` w logu bez wpisów błędu. Stary log jest przenoszony do `openmw.previous.log`, żeby nie zaliczyć poprzedniego wyniku. Test ma limit 180 sekund.
- `Graj.exe --check` sprawdza przygotowanie profilu i ścieżek bez tworzenia okna gry; jest używany przez CI i nie jest testem rozgrywki.

Launcher jest natywnym programem Windows z interfejsem plikowym UTF-16 i konfiguracją UTF-8 bez BOM. Przekazuje silnikowi względny argument `--config`, aby uniknąć utraty polskich znaków podczas konwersji argumentów przez Windows CRT. Uruchamia silnik z jego własnego katalogu i nie korzysta z globalnego profilu OpenMW.

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

Na Linuksie potrzebne są 7-Zip i kompilator MinGW-w64:

```sh
python3 tools/setup.py --platform windows
python3 tools/package_windows.py
```

Niestandardowe lokalizacje narzędzi można wskazać przez `--seven-zip` w instalatorze i `--compiler` w pakowarce. ZIP zawiera wyłącznie przygotowany runtime, bieżące zasoby, kod gry, testy i informacje o licencjach. Zawartość dodatku jest generowana od nowa w katalogu tymczasowym; lokalne zapisy, logi, poprzednie modele robocze i dane Git nie trafiają do paczki. `manifest.json` rejestruje sumy wszystkich plików paczki.

**Zakres weryfikacji**

W obecnej maszynie sprawdzono 10 testów narzędzi, regresję 12 testów na Linuksie i 12 testów silnika Windows uruchomionego przez Wine 10/Mesa. Weryfikacja wersji Windows obejmowała natywny `Graj.exe`, folder ze spacjami i literą „Ł”, renderowanie, walkę, kolizje, nagrody, restart oraz rzeczywisty zapis i wczytanie. To weryfikacja binariów Windows przez warstwę zgodności; nie jest pomiarem na komputerze Windows z docelową kartą graficzną.

Workflow Windows dodatkowo wykonuje testy narzędzi, sprawdza wersję natywnego silnika, kompiluje launcher przez MSVC i sprawdza generowanie profilu Unicode. Nie traktuje testu `--check` jako testu renderowania; pełną regresję gry wykonuje osobne zadanie linuksowe.
