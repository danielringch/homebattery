Tricks
======

Starting up Hoymiles inverters without current limiting device
--------------------------------------------------------------

Hoymiles inverters have large capacitors directly connected to their input. As a consequence, there is a huge current spike when connecting a voltage source. This can lead to arks and damage the battery electronics.

Many people use current limiting circuits (aka soft-start), but they have several downsides:

* they might be a fire hazard if they fail
* they add complexity
* they cost money.

Homebattery is designed to have the inverter directly connected to the battery, a fuse is used for safety. This way, the capacitors are always charged and no current limiting is necessary.

A little care is necessary if the system is shutdown for maintenance. After the batteries were disconnected, the following steps will bring your system back online without causing current spikes:

* turn off homebattery
* turn both grid and solar chargers off
* switch all batteries to protection mode (all MOS switches off) via your BMS software
* ensure everything is really off using a multimeter
* connect all inverters
* turn on the solar charger or grid charger
* wait until the inverter LED starts to blink
* switch all batteries to normal mode (all MOS switches on) via your BMS software
* turn off the solar/ grid charger
* turn on homebattery

So basically the inverter input capacitors are charged by turning on the solar/ grid charger, which prevents any current spike.

