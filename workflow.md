# Dolvac Hardware Workflow

Cały workflow opiera się na:
* Kicad
* DolvacHWScripts (dhs)
* DolvacComponentsLibrary (dcl)
* Git (i repozytorium gitea)

Projekty schematów i PCB przygotowywane są w Kicadzie z użyciem komponentów z biblioteki DolvacComponentsLibrary.
W procesie projektowania pomagają skrypty z DolvacHWScripts, np. ustawiają wartości z szablonów, tworzą pliki produkcyjne.
Projekty przechowywane są git'cie na gitei.

## Tworzenie nowego projektu
- stworzyć nowe repozytorium na gitea w organizacji dolvac z zaznaczoną opcją private
- sklonować repozytorium lokalnie (git clone adres_ssh)
- stworzyć nowy projekt kicad w subfolderze `hw`
- użyć skryptu do ustawienia wartości domyślnych (`dhs templates all`)
-  