# Beautiful Time Tracker

En enkel och elegant time-tracker för Ubuntu/Linux med GTK-gränssnitt och smart hantering av tiden när du är borta från datorn.

## Funktioner

### Huvudfunktioner
- **Tidsspårning**: Logga tid på olika uppgifter/projekt
- **Smart unlock-hantering**: När du låser/stänger av datorn och sedan loggar in igen får du en dialog som frågar vad du vill göra med tiden du var borta
- **Ubuntu-integration**: Nativt GTK-gränssnitt som passar perfekt in i Ubuntu
- **Autostart**: Startar automatiskt när du loggar in
- **Persistens**: All data sparas i en lokal SQLite-databas

### Smart Unlock-dialog
När du kommer tillbaka till datorn efter att ha låst den visas en dialog som:
- Visar hur länge du var borta
- Påminner dig om vilken uppgift du arbetade på
- Ger dig tre alternativ:
  1. **Fortsätt logga på samma uppgift** - tiden du var borta läggs till på uppgiften
  2. **Logga på en annan uppgift** - välj en annan uppgift att logga tiden på
  3. **Logga inte tiden** - skippa tiden helt

## Installation

### Krav
- Ubuntu 20.04 eller senare (eller liknande Linux-distribution med GTK 3)
- Python 3.8 eller senare
- Poetry (installeras automatiskt av installationsskriptet om det saknas)

### Installationssteg

1. Klona eller ladda ner detta projekt:
```bash
cd /home/user
git clone <repository-url> beatuful-timetracker
cd beatuful-timetracker
```

2. Kör installationsskriptet:
```bash
./install.sh
```

Installationsskriptet kommer att:
- Installera Poetry om det inte finns
- Installera nödvändiga Python-paket med Poetry
- Konfigurera autostart så att programmet startar automatiskt vid inloggning
- Skapa en desktop-fil

3. Starta programmet:
```bash
poetry run python timetracker.py
# Eller
poetry run timetracker
```

Eller hitta det i din applikationsmeny under "Beautiful Time Tracker".

## Användning

### Skapa en uppgift
1. Klicka på "Ny uppgift"
2. Ange ett namn på uppgiften
3. Klicka "Skapa"

### Börja logga tid
1. Välj en uppgift i listan
2. Klicka "Starta tidsinmatning"
3. Timern börjar räkna

### Stoppa tidsinmatning
1. Klicka "Stoppa tidsinmatning"
2. Tiden sparas automatiskt på uppgiften

### Hantera tid efter unlock
När du låser datorn medan tidsinmatning pågår och sedan loggar in igen:
1. En dialog visas automatiskt
2. Välj vad du vill göra med tiden du var borta
3. Klicka OK

## Teknisk information

### Arkitektur
- **GUI**: GTK 3 via PyGObject
- **Databas**: SQLite
- **Lock/Unlock-detection**: DBus (lyssnar på org.gnome.ScreenSaver och org.freedesktop.login1)

### Databasplacering
All data sparas i:
```
~/.local/share/timetracker/timetracker.db
```

### Filer
- `timetracker.py` - Huvudapplikation och DBus-hantering
- `main_window.py` - Huvudfönster med uppgiftslista och timer
- `unlock_dialog.py` - Dialog som visas efter unlock
- `database.py` - Databashantering
- `pyproject.toml` - Poetry-konfiguration och Python-beroenden
- `install.sh` - Installationsskript
- `timetracker.desktop` - Desktop-fil för autostart

## Avinstallation

```bash
# Ta bort autostart
rm ~/.config/autostart/timetracker.desktop

# Ta bort programmet
rm -rf /home/user/beatuful-timetracker

# (Valfritt) Ta bort databasen
rm -rf ~/.local/share/timetracker
```

## Felsökning

### Programmet startar inte automatiskt
Kontrollera att autostart-filen finns:
```bash
ls ~/.config/autostart/timetracker.desktop
```

Om den saknas, kör installationsskriptet igen:
```bash
./install.sh
```

### Unlock-dialogen visas inte
Programmet lyssnar på DBus-signaler från GNOME ScreenSaver och systemd login1.
Kontrollera att dessa tjänster körs:
```bash
# Kontrollera om ScreenSaver är tillgänglig
dbus-send --session --print-reply --dest=org.gnome.ScreenSaver /org/gnome/ScreenSaver org.freedesktop.DBus.Introspectable.Introspect
```

### Python-beroenden saknas
Installera manuellt med Poetry:
```bash
poetry install
```

Eller om Poetry inte är installerat:
```bash
# Installera Poetry först
curl -sSL https://install.python-poetry.org | python3 -

# Lägg till Poetry i PATH
export PATH="$HOME/.local/bin:$PATH"

# Installera beroenden
poetry install
```

## Utveckling

Bidrag välkomnas! Programmet är skrivet i Python med GTK 3 och använder Poetry för beroendehantering.

### Köra utan installation
```bash
# Installera Poetry om du inte har det
curl -sSL https://install.python-poetry.org | python3 -

# Installera beroenden
poetry install

# Kör programmet
poetry run python timetracker.py
```

### Lägga till nya beroenden
```bash
# Lägg till ett produktionsberoende
poetry add paketnamn

# Lägg till ett utvecklingsberoende
poetry add --group dev paketnamn
```

### Skapa en virtuell miljö manuellt
Poetry skapar och hanterar virtuella miljöer automatiskt, men du kan också:
```bash
# Aktivera Poetry's virtuella miljö
poetry shell

# Nu kan du köra python direkt
python timetracker.py
```

### Köra tester
Projektet har ett omfattande test-suite som testar alla viktiga funktioner.

```bash
# Installera dev-dependencies (inkluderar pytest)
poetry install

# Kör alla tester
poetry run pytest

# Kör tester med verbose output
poetry run pytest -v

# Kör tester med coverage-rapport
poetry run pytest --cov=. --cov-report=html

# Kör endast databastester
poetry run pytest tests/test_database.py

# Kör endast unlock-logik-tester
poetry run pytest tests/test_unlock_logic.py

# Kör ett specifikt test
poetry run pytest tests/test_database.py::TestTaskManagement::test_add_task
```

**Test-coverage:**
- `test_database.py` - Omfattande tester för alla databasfunktioner
  - Task management (skapa, hämta uppgifter)
  - Time entries (starta, stoppa, beräkna duration)
  - Session state (lock/unlock state)
  - Edge cases (midnight-spanning, noll-duration, etc.)
- `test_unlock_logic.py` - Tester för unlock-scenariot
  - Fortsätt på samma uppgift
  - Byt till annan uppgift
  - Skippa tiden
  - Flera lock/unlock-cykler
  - Session state integrity

## Licens

MIT License - Se LICENSE-filen för detaljer.

## Författare

Skapat för att lösa det verkliga problemet med att hantera tid när man lämnar datorn under arbetsdagen.
