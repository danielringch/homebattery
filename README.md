# homebattery

Welcome to the homebattery project.

## What is homebattery?

Homebattery is an all-in-one control solution for home battery storage, consisting of:
* the hardware based on a Raspberry Pi Pico
* all necessary software
* extensive documentation

## Why homebattery?

There are other solutions for controlling a home battery, both commercial and DIY. But homebattery has some nice characteristics that might be interesting for you:
* **reliability**: the whole project was designed with operational safety in mind. Too much to go into detail here, there is a whole section in the documentation about this
* **simplicity**: homebattery does not have fancy stuff that looks shiny, but makes things complicated. The whole system is basically controlled via a bunch of MQTT topics
* **Home Assistant integration**: homebattery itself is an embedded solution working as a backend. With the integration into Home Assistant, sky is the limit. (You could also write a custom frontend if you want, the documentation explains how.)

## What do I need?

* **a Raspberry Pi Pico W**. If you want to have a display and LEDs, or want to use hardware connected to homebattery via cable, you will also need the baseboard and maybee some add-on boards.
* **a Home Assistant instance**. Or any other frontend.
* **compatible hardware**. See the list below.

## What hardware is supported?

### Battery

* **LLT Power BMS with Bluetooth** via Bluetooth LE
    * tested Battery: Accurat Traction T60 LFP BT 24V
    * Many other LiFePo4 Batteries with Bluetooth BMS seem to have this kind of BMS
* **Daly H-Series Smart BMS with Bluetooth** via Bluetooth LE
    * tested BMS: 8S 60A variant
* **JK BMS BD4-Series** via Bluetooth LE
    * tested BMS: BD4A17S4P

### Solar charger

* **Victron SmartSolar MPPT** via VE.Direct
    * tested model: Smartsolar MPPT 75/15
    * requires baseboard and VE.Direct add-on board
* **Victron BlueSolar MPPT** vis VE.Direct
    * tested model: none, but the protocol is well documented to be the same as for the SmartSolar variants
    * requires baseboard and VE.Direct add-on board
    * please keep in mind that homebattery can not change the configuration of the charger, for this you might need the Victron USB interface

### Grid charger

* any model switched by a **Shelly smart switch** via network
    * tested model: Shelly Plus2PM, Shelly Plus1PM

### Inverter

* Hoymiles inverters controlled by **AhoyDTU** via network
    * tested model: HM-300

## How to start?

Please read the complete guide in the documentation.

## Disclaimer

While homebattery was designed with high operational safety in mind and is used every day in my own house, there is no warranty for anything.
Please keep in mind that a home battery storage comes with stuff that can cause a fire or explosion if done wrong:
* high currents
* chemicals storing a high amount of energy

The quality of the electical setup is crucial. So please ensure that it is done by someone knowing what he or she is doing and, maybe even more important, care about maintenance.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## MQTT topics

XXX/charger/state (ro)
XXX/inverter/state (ro)
XXX/inverter/power (ro)
XXX/mode (wo) [idle, charge, discharge]
XXX/locked (ro)


XXX/live/consumption (ro)