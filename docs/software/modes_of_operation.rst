Modes of operation
==================

.. note::
   Mode ``grid`` is not implemented yet.

Systems with grid tie inverter
------------------------------

+--------------+---------+-------+----------+
| Mode         | Charger | Solar | Inverter |
+==============+=========+=======+==========+
| charge       | on      | on    | off      |
+--------------+---------+-------+----------+
| grid         | on      | on    | off      |
+--------------+---------+-------+----------+
| idle         | off     | on    | off      |
+--------------+---------+-------+----------+
| discharge    | off     | on    | on       |
+--------------+---------+-------+----------+
| protect      | off     | off   | off      |
+--------------+---------+-------+----------+

The mode ``grid`` is not relevant for systems with grid tie inverters, as it behaves the same way as the mode ``charge``.

Systems with hybrid inverter
----------------------------

+--------------+---------------------+----------------------+
| Mode         | Battery charged via | Output fed from      |
+==============+=====================+======================+
| charge       | solar + grid        | grid                 |
+--------------+---------------------+----------------------+
| grid         | solar               | grid                 |
+--------------+---------------------+----------------------+
| idle         | surplus solar       | solar + grid         |
+--------------+---------------------+----------------------+
| discharge    | surplus solar       | solar + battery      |
+--------------+---------------------+----------------------+
| protect      | none                | grid                 |
+--------------+---------------------+----------------------+

The mode ``grid`` is useful to charge the battery from solar in winter during medium or low energy prices. Solar production in winter can usually not fully cover the energy demand of a home, but it would be economic to store the solar energy in the battery and use it when the energy prices are high.
