dpkg --add-architecture i386
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y wine wine32 wine64 winetricks wget curl
