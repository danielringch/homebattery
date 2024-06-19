# homebattery

Welcome to the homebattery project.

<img src="docs/images/whole_box.png" alt="homebattery" height="300"/>
<img src="docs/images/system_overview.png" alt="homebattery" height="300"/>

## What is homebattery?

Homebattery is am embedded controller for your home battery storage (or EV charger). The goal of homebattery is to

* save money with dynamic energy pricing by charging and discharging the battery depending on the current price
* add another level of safety to our system by monitoring all safety relevant device parameters
* combine devices that are not compatible without a little help (e.g. charge Pylontech batteries with Victron MPPT solar chargers)
* make devices controllable and monitorable via a common MQTT interface

Homebattery comes with:

* its own hardware based on a Raspberry Pi Pico W 
  * some simple setups even work with a bare Raspberry Pi Pico W
* the homebattery firmware for Raspberry Pi Pico W 
* extensive documentation: http://homebattery.readthedocs.io

## Why homebattery?

Homebattery was not the first and will not be the last solution for controlling your home battery storage, but it has some nice features you might be interested in:

* **reliability**: by using an embedded system with a watchdog timer, homebattery is much more reliable than a bare home automation solution.
* **safety checks**: ensure that all device parameters are in the green range. If not, homebattery reacts accordingly, e.g. by turning off the inverter if the SOC of the battery gets too low.
* **simplicity** is achieved by a clear feature set. Controls the hardware, the business logic is implemented in your home automation solution
* **modularity** is the result of using drivers to communicate with devices. So by adding more drivers, homebattery will support even more hardware in the future. Also the hardware is modular, so a variety of physical interfaces (Bluetooth, ethernet, RS485, VE.Direct, ...) are supported.
* **MQTT** is used to communicate with homebattery. So everything with MQTT support can be used to controll homebattery (Home Assistant, ioBroker, etc.). The MQTT interface is well documented.

## What do I need?

* **homebattery hardware**. If you only connect devices via network and Bluetooth, even a bare Raspberry Pi Pico W will do the job.
* **a smart home solution** like Home Assistant or ioBroker. You can use any software that is capable of MQTT.
* **compatible devices**. See the list below.

## What hardware is supported?

| Group | Device family | Tested devices | Connection method | Remarks |
| - | - | - | - | - |
| battery | LLT Power BMS | Accurat Traction T60 LFP BT 24V | Bluetooth         | many China LiFePo4 batteries use this BMS |
| | Daly H-Series Smart BMS | Daly H-Series Smart BMS 8S 60A | Bluetooth | - |
| | JK BMS BD4-Series | BD4A17S4P | Bluetooth | - |
| solar charger | Victron SmartSolar MPPT | Smartsolar MPPT 75/15 | VE.Direct | - |
| | Victron BlueSolar MPPT | - | VE.Direct | configuration is still done via Victron USB interface |
| grid charger | Shelly smart switch | Shelly Plus2PM<br>Shelly Plug S | network | - |
| inverter | Hoymiles HM-Series | HM-300 | network | requires AhoyDTU |

## How to start?

Please read the handbook in the documentation.

## Disclaimer

While homebattery was designed with high operational safety in mind and has already some installations deployed, there is no warranty for anything.
Please keep in mind that a home battery storage comes with stuff that can cause a fire or explosion if done wrong:
* high currents
* chemicals storing a high amount of energy

The quality of the electical setup is crucial. So please ensure that it is done by someone knowing what he or she is doing and, maybe even more important, care about maintenance.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
