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
- pip3

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
- Installera nödvändiga Python-paket
- Konfigurera autostart så att programmet startar automatiskt vid inloggning
- Skapa en desktop-fil

3. Starta programmet:
```bash
python3 timetracker.py
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
- `requirements.txt` - Python-beroenden
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
Installera manuellt:
```bash
pip3 install --user PyGObject pydbus
```

## Utveckling

Bidrag välkomnas! Programmet är skrivet i Python med GTK 3.

### Köra utan installation
```bash
# Installera beroenden
pip3 install --user -r requirements.txt

# Kör programmet
python3 timetracker.py
```

## Licens

MIT License - Se LICENSE-filen för detaljer.

## Författare

Skapat för att lösa det verkliga problemet med att hantera tid när man lämnar datorn under arbetsdagen.
