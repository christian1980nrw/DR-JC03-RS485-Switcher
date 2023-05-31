# DR-JC03-RS485-Switcher
Script that reads out SOC, voltage and current of a DR-JC03 BMS / Protocol DR-1363 (RS485 with the delivered RJ45 Adapter)
and turns on switchable sockets depending voltage or SOC.

![grafik](https://github.com/christian1980nrw/DR-JC03-RS485-Switcher/assets/6513794/1cf3100c-3362-421b-b357-3cc3c7047307)

# Installation (tested with Victron Venus OS)

I set my battery to ID1 (first DIP switch ON).

Copy everything to /data/ and chmod it to executable.

Setup your switchable sockets (Shelly Plug S or AVM DECT switchable sockets) at turnon.sh and turnoff.sh.

Setup the correct USB-Port at /data/soc_switcher.py. The command  "dmesg | grep tty" is usable to find it out.
I was using the RJ45 to RS485 USB adapter that came with the battery.

Test the script with /usr/bin/python /data/soc_switcher.py

Insert the folowing to /data/rc.local:
/data/run_soc_switcher.sh >/dev/null 2>&1 &

reboot and check if the script is running automatically with:
pgrep -f "python /data/soc_switcher.py" (it should display a ID).



