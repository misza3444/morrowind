# Walidacja pierwszego prototypu

Sprawdzenie 21 października 2026 r. w przygotowanym środowisku Linux x86_64: OpenMW 0.51.0, Python 3.12.14, Xorg dummy i Mesa llvmpipe. Nie używano plików Morrowinda ani zmodyfikowanego silnika.

Komenda: `python3 tools/run.py --test --headless`.

Zestaw wykonuje kod gry w silniku i sprawdza:

1. Start w samodzielnej arenie, fizyczną kolizję podłoża, HP gracza, trzech wrogów, kamerę oraz wyposażenie broni.
2. Reguły combo dla kroków czasu odpowiadających 30, 60 i 120 FPS: trzy trafienia i 74 obrażenia. To test czasu reguł Lua, nie pomiar renderowania ani fizyki przy tych FPS.
3. Wybranie celu, rzeczywisty obrót postaci w jego kierunku i zwolnienie celu.
4. Odtwarzanie animacji trzech ciosów oraz dokładnie 74 obrażenia przekazane przez zdarzenia silnika.
5. Brak trafienia poza zasięgiem.
6. Brak obrażeń przez fizyczną ścianę.
7. Nietykalność podczas uniku, przyjmowanie obrażeń po jej zakończeniu i przywrócenie szybkości.
8. Przesunięcie prawdziwej postaci podczas uniku i zatrzymanie na ścianie.
9. Obrażenia obu zdolności i blokadę ponownego użycia podczas odnowienia.
10. Zwycięstwo i jednorazową nagrodę mimo powtórzonego zdarzenia śmierci.
11. Restart po zwycięstwie i porażce, przywrócenie HP i zachowanie nagrody.
12. Rzeczywisty zapis `.omwsave` oraz wczytanie: nagroda, odnowienie zdolności, HP i trzech przeciwników bez powielania.

Wynik: **12 sprawdzeń zakończonych powodzeniem**, znacznik `EH_TESTS_PASSED`, proces silnika zakończony kodem 0. Runner odrzuca test także wtedy, gdy w logu silnika występuje wpis błędu `E`. Log znajduje się w `.runtime/test-profile/openmw.log` i jest nadpisywany przy następnym uruchomieniu.

Zrzut sceny wykonano poleceniem `python3 tools/run.py --headless --capture build/echo-arena.png`. To obraz z uruchomionego OpenMW, nie wizualizacja koncepcyjna.

Dodatkowo wysłano rzeczywiste zdarzenia klawiatury przez XTest do okna gry: Q uruchomiło zdolność i jej odnowienie, Tab namierzyło przeciwnika, a F6 utworzyło natywny plik `.omwsave`. Kadr po tych zdarzeniach zapisano w [images/combat.png](images/combat.png). To dodatkowe sprawdzenie wejścia; nie jest częścią powtarzalnego zestawu 12 testów ani oceną sterowania przez gracza.

Pozostają ostrzeżenia upstream dotyczące kanału UV modeli COLLADA i nazw części kości przykładowego stworzenia. Nie uniemożliwiły renderowania ani testowanych animacji. Prototyp nie jest jeszcze oceną jakości docelowej walki. Brak pomiarów na GPU gracza, testów gamepada, długich sesji i migracji zapisów między wersjami. Testy walki uruchamiają publiczny interfejs kontrolera; nie zastępują oceny responsywności klawiatury i myszy przez gracza.

Obsługę Windows i osobną weryfikację binariów Windows przez Wine opisuje [WINDOWS.md](WINDOWS.md). Po zmianach narzędzi uruchomiono ponownie 12 testów regresji Linuksa i 10 testów narzędzi, w tym zachowanie ustawień, ścieżki Unicode, odrzucanie błędnej sumy i obsługę procesu Windows.

Pierwszy przebieg CI Windows wykazał błędne oczekiwanie testu dotyczące zakończeń wierszy: poprawny plik CRLF porównywano z tekstem LF. Błąd odtworzono windowsowym Pythonem 3.12 przez Wine. Po poprawce test sprawdza całe linie niezależnie od formatu zakończeń; wszystkie 10 testów narzędzi przeszło zarówno na Linuksie, jak i w windowsowym Pythonie przez Wine.

Po dołączeniu gotowych modeli świątyni i wyposażenia z Example Suite ponownie przeszło 12 testów silnika na Linuksie oraz 12 testów z gotowej paczki Windows przez Wine. Dodatkowy test narzędzi sprawdza kopiowanie zweryfikowanego modelu wraz z manifestem oraz odrzucenie brakującego pliku, zmienionych bajtów i niepobranego wskaźnika LFS. Obecny zestaw obejmuje 11 testów narzędzi; przeszedł na Linuksie i w windowsowym Pythonie przez Wine. Rzeczywisty wygląd nowych modeli i tekstury podłoża sprawdzono w silniku; kadr znajduje się w [images/temple.png](images/temple.png).

Aktualizator dodaje 15 testów transakcji: pierwszą instalację, użycie niezmienionego runtime, brak ponownego pobierania tej samej wersji, uszkodzony ZIP i plik, brakujący plik, niedozwolone ścieżki i powtórzenia nazw, anulowanie, przerwanie przed przełączeniem, powrót do poprzedniej wersji, naprawę danych i metadanych oraz wykorzystanie starej płaskiej instalacji. Osobny test odtwarza całą grę z rzeczywistych paczek publikacji i porównuje sumy plików. Testy publikowania zwiększają zestaw Pythona do 14 i sprawdzają odrzucenie uszkodzonej paczki oraz starszego przebiegu CI i kolejność publikacji przed zmianą kanału.

Sprawdzono też cały łańcuch EXE Windows przez Wine 10 z Wine Mono 9.4: bootstrap `Graj.exe`, aktualizator .NET, natywny `Uruchom.exe` i OpenMW. W folderze ze spacjami i „Ł” przeszły przygotowanie profilu i 12 testów gry. Mały pakiet launchera rozpakowano również do starej płaskiej paczki; tryb `--check` zachował istniejące ustawienia i zapis kontrolny. Weryfikacja obejmuje 943 pliki wersji i osobne pliki bootstrapa. Nie potwierdza jeszcze pobrania z kanału GitHub na komputerze użytkownika; wymaga to udanego zadania publikacji i publicznego repozytorium.
