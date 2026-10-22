export DISPLAY=:1
export WINEPREFIX=/config/.wine
export WINEARCH=win64
wineboot --init
winetricks -q win10
