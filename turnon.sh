#!/bin/bash


# Switchable Sockets Setup (AVM Fritz DECT200/210 wireless sockets) if used (tested with FRITZ!OS: 07.29).
use_fritz_dect_sockets=1 # please activate with 1 or deactivate this socket-type with 0
fbox="192.168.188.1"
user="fritz1234"
passwd="YOURPASSWORD"
sockets=("YOURSOCKETID" "0" "0" "0" "0" "0")

# Switchable Sockets Setup (Shelly Wifi Plugs) (tested with Shelly Plug S Firmware 20230109-114426/v1.12.2-g32055ee)
use_shelly_wlan_sockets=0  # please activate with 1 or deactivate this socket-type with 0
shelly_ips=("192.168.188.89" "0" "0") # add multiple Shellys if you like, dont forget to make the ips static in your router
shellyuser="admin"
shellypasswd="YOURPASSWORD" # only if used


# execute Fritz DECT on command
if (( use_fritz_dect_sockets == 1 )); then
# Get session ID (SID)
sid=""
challenge=$(curl -s "http://$fbox/login_sid.lua" | grep -o "<Challenge>[a-z0-9]\{8\}" | cut -d'>' -f 2)
	if [ -z "$challenge" ]; then
    printf "Error: Could not retrieve challenge from login_sid.lua.\n"
    exit 1
	fi

hash=$(echo -n "$challenge-$passwd" |sed -e 's,.,&\n,g' | tr '\n' '\0' | md5sum | grep -o "[0-9a-z]\{32\}")
sid=$(curl -s "http://$fbox/login_sid.lua" -d "response=$challenge-$hash" -d "username=$user" \
    | grep -o "<SID>[a-z0-9]\{16\}" |  cut -d'>' -f 2)
	if [ "$sid" = "0000000000000000" ]; then
    printf "Error: Login to Fritzbox failed.\n"
    exit 1
	fi
printf "Login to Fritzbox successful.\n"
# Iterate over each socket
for socket in "${sockets[@]}"; do
    if [ "$socket" = "0" ]; then
        continue
    fi

    # Get state and connectivity of socket
    connected=$(curl -s "http://$fbox/webservices/homeautoswitch.lua?sid=$sid&ain=$socket&switchcmd=getswitchpresent")
    state=$(curl -s "http://$fbox/webservices/homeautoswitch.lua?sid=$sid&ain=$socket&switchcmd=getswitchstate")

    if [ "$connected" = "1" ]; then
        printf "Turning socket $socket on...\n" | tee -a $LOG_FILE
        curl -s "http://$fbox/webservices/homeautoswitch.lua?sid=$sid&ain=$socket&switchcmd=setswitchon" >/dev/null
    else
        printf "Socket $socket is not connected\n" | tee -a $LOG_FILE
    fi
done
fi

  if (( use_shelly_wlan_sockets == 1 )); then
  
  for ip in "${shelly_ips[@]}"
do
  if [ $ip != "0" ]; then
    echo "Turning Shelly on." | tee -a $LOG_FILE
    curl -u '$shellyuser:$shellypasswd' http://$ip/relay/0?turn=on
  fi
done
  fi
