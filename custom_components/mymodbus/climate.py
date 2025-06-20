"""
Platform for a Generic Modbus Thermostat.

For more details about this platform, please refer to the documentation at
https://github.com/Yonsm/ZhiModBus
"""

import logging
import struct

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
from homeassistant.components.climate.const import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import CONF_NAME, CONF_SLAVE, CONF_OFFSET, CONF_STRUCTURE, ATTR_TEMPERATURE
from homeassistant.components.modbus.const import (
    DEFAULT_HUB, MODBUS_DOMAIN,
    CALL_TYPE_COIL, CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_COIL, CALL_TYPE_WRITE_REGISTER
)
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

CONF_AUX_HEAT_OFF_VALUE = 'aux_heat_off_value'
CONF_AUX_HEAT_ON_VALUE = 'aux_heat_on_value'
CONF_COUNT = 'count'
CONF_DATA_TYPE = 'data_type'
CONF_FAN_MODES = 'fan_modes'
CONF_HVAC_MODES = 'hvac_modes'
CONF_HVAC_OFF_VALUE = 'hvac_off_value'
CONF_HVAC_ON_VALUE = 'hvac_on_value'
CONF_PRESET_MODES = 'preset_mode'
CONF_REGISTER = 'register'
CONF_REGISTER_TYPE = 'register_type'
CONF_REGISTERS = 'registers'
CONF_REVERSE_ORDER = 'reverse_order'
CONF_SCALE = 'scale'
CONF_SWING_MODES = 'swing_modes'

REG_AUX_HEAT = 'aux_heat'
REG_FAN_MODE = 'fan_mode'
REG_FAN_MODE_SET = 'fan_mode_set'
REG_HUMIDITY = 'humidity'
REG_HVAC_MODE = 'hvac_mode'
REG_HVAC_MODE_SET = 'hvac_mode_set'
REG_HVAC_ON_OFF = 'hvac_onoff'
REG_HVAC_ON_OFF_SET = 'hvac_onoff_set'
REG_PRESET_MODE = 'preset_mode'
REG_SWING_MODE = 'swing_mode'
REG_TARGET_HUMIDITY = 'target_humidity'
REG_TARGET_TEMPERATURE = 'target_temperature'
REG_TARGET_TEMPERATURE_SET = 'target_temperature_set'
REG_TEMPERATURE = 'temperature'

REGISTER_TYPE_HOLDING = 'holding'
REGISTER_TYPE_INPUT = 'input'
REGISTER_TYPE_COIL = 'coil'

DATA_TYPE_INT = 'int'
DATA_TYPE_UINT = 'uint'
DATA_TYPE_FLOAT = 'float'
DATA_TYPE_CUSTOM = 'custom'

SUPPORTED_FEATURES = {
    REG_FAN_MODE_SET: ClimateEntityFeature.FAN_MODE,
    REG_FAN_MODE: 0,
    REG_HUMIDITY: 0,
    REG_HVAC_MODE: 0,
    REG_HVAC_MODE_SET: ClimateEntityFeature.TURN_ON,
    REG_HVAC_ON_OFF_SET: ClimateEntityFeature.TURN_OFF,
    REG_HVAC_ON_OFF: 0,
    REG_PRESET_MODE: ClimateEntityFeature.PRESET_MODE,
    REG_SWING_MODE: ClimateEntityFeature.SWING_MODE,
    REG_TARGET_HUMIDITY: ClimateEntityFeature.TARGET_HUMIDITY,
    REG_TARGET_TEMPERATURE_SET: ClimateEntityFeature.TARGET_TEMPERATURE,
    REG_TARGET_TEMPERATURE: 0,
    REG_TEMPERATURE: 0,
}

HVAC_ACTIONS = {
    HVACMode.OFF: HVACAction.OFF,
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.HEAT_COOL: HVACAction.IDLE,
    HVACMode.AUTO: HVACAction.IDLE,
    HVACMode.DRY: HVACAction.DRYING,
    HVACMode.FAN_ONLY: HVACAction.FAN,
}

DEFAULT_NAME = 'ModBus'
CONF_HUB = 'hub'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): vol.Any(cv.string, list),

    vol.Optional(CONF_FAN_MODES, default={}): dict,
    vol.Optional(CONF_HVAC_MODES, default={}): dict,
    vol.Optional(CONF_PRESET_MODES, default={}): dict,
    vol.Optional(CONF_SWING_MODES, default={}): dict,
    vol.Optional(CONF_AUX_HEAT_OFF_VALUE, default=0): int,
    vol.Optional(CONF_AUX_HEAT_ON_VALUE, default=1): int,
    vol.Optional(CONF_HVAC_OFF_VALUE, default=0): int,
    vol.Optional(CONF_HVAC_ON_VALUE, default=1): int,

    vol.Optional(REG_AUX_HEAT): dict,
    vol.Optional(REG_FAN_MODE): dict,
    vol.Optional(REG_FAN_MODE_SET): dict,
    vol.Optional(REG_HUMIDITY): dict,
    vol.Optional(REG_HVAC_MODE): dict,
    vol.Optional(REG_HVAC_MODE_SET): dict,
    vol.Optional(REG_HVAC_ON_OFF): dict,
    vol.Optional(REG_HVAC_ON_OFF_SET): dict,
    vol.Optional(REG_PRESET_MODE): dict,
    vol.Optional(REG_SWING_MODE): dict,
    vol.Optional(REG_TARGET_HUMIDITY): dict,
    vol.Optional(REG_TARGET_TEMPERATURE): dict,
    vol.Optional(REG_TARGET_TEMPERATURE_SET): dict,
    vol.Optional(REG_TEMPERATURE): dict,
})


def setup_platform(hass, conf, add_devices, discovery_info=None):
    """Set up the Modbus Thermostat Platform."""
    name = conf.get(CONF_NAME)
    bus = ClimateModbus(hass, conf)
    if not bus.regs:
        _LOGGER.error("Invalid config %s: no modbus items", name)
        return

    entities = []
    for index in range(100):
        if not bus.has_valid_register(index):
            break
        entities.append(MyModbusClimate(bus, name[index] if isinstance(name, list) else (name + str(index + 1)), index))

    if not entities:
        for prop in bus.regs:
            if CONF_REGISTER not in bus.regs[prop]:
                _LOGGER.error("Invalid config %s/%s: no register", name, prop)
                return
        entities.append(MyModbusClimate(bus, name[0] if isinstance(name, list) else name))

    bus.count = len(entities)
    add_devices(entities, True)


class ClimateModbus():

    def __init__(self, hass, conf):
        self.error = 0
        self.hass = hass
        self.hub = self.hass.data[MODBUS_DOMAIN][conf.get(CONF_HUB)]
        self.unit = hass.config.units.temperature_unit
        self.fan_modes = conf.get(CONF_FAN_MODES)
        self.hvac_modes = conf.get(CONF_HVAC_MODES)
        self.preset_modes = conf.get(CONF_PRESET_MODES)
        self.swing_modes = conf.get(CONF_SWING_MODES)
        self.hvac_off_value = conf.get(CONF_HVAC_OFF_VALUE)
        self.hvac_on_value = conf.get(CONF_HVAC_ON_VALUE)
        self.aux_heat_on_value = conf.get(CONF_AUX_HEAT_ON_VALUE)
        self.aux_heat_off_value = conf.get(CONF_AUX_HEAT_OFF_VALUE)

        data_types = {DATA_TYPE_INT: {1: 'h', 2: 'i', 4: 'q'}}
        data_types[DATA_TYPE_UINT] = {1: 'H', 2: 'I', 4: 'Q'}
        data_types[DATA_TYPE_FLOAT] = {1: 'e', 2: 'f', 4: 'd'}

        self.regs = {}
        for prop in SUPPORTED_FEATURES:
            reg = conf.get(prop)
            if not reg:
                continue

            count = reg.get(CONF_COUNT, 1)
            data_type = reg.get(CONF_DATA_TYPE)
            if data_type != DATA_TYPE_CUSTOM:
                try:
                    reg[CONF_STRUCTURE] = '>{}'.format(data_types[DATA_TYPE_INT if data_type is None else data_type][count])
                except KeyError:
                    _LOGGER.error("Unable to detect data type for %s", prop)
                    continue

            try:
                size = struct.calcsize(reg[CONF_STRUCTURE])
            except struct.error as err:
                _LOGGER.error("Error in sensor %s structure: %s", prop, err)
                continue

            if count * 2 != size:
                _LOGGER.error("Structure size (%d bytes) mismatch registers count (%d words)", size, count)
                continue

            self.regs[prop] = reg

    def has_valid_register(self, index):
        """Check valid register."""
        for prop in self.regs:
            registers = self.regs[prop].get(CONF_REGISTERS)
            if not registers or index >= len(registers):
                return False
        return True

    def reset(self):
        """Initialize USR module"""
        _LOGGER.warn("Reset %s", self.hub._client)
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((self.hub._pb_params["host"], self.hub._pb_params["port"]))
        s.sendall(b'\x55\xAA\x55\x00\x25\x80\x03\xA8')
        s.close()

    async def reconnect(self, now=None):
        _LOGGER.warn("Reconnect %s", self.hub._client)
        await self.hub.async_restart()

    def exception(self):
        """
        turns = int(self.error / self.count)
        self.error += 1
        if turns != 0 and (turns > 6 and turns % 10):
            return
        if turns % 3 == 0:
            self.reset()"""
        from homeassistant.helpers.event import async_call_later
        async_call_later(self.hass, 1, self.reconnect)

    def reg_basic_info(self, reg, index):
        """Get register info."""
        register_type = reg.get(CONF_REGISTER_TYPE)
        register = reg[CONF_REGISTER] if index == -1 else reg[CONF_REGISTERS][index]
        slave = reg.get(CONF_SLAVE, 1)
        scale = reg.get(CONF_SCALE, 1)
        offset = reg.get(CONF_OFFSET, 0)
        return (register_type, slave, register, scale, offset)

    async def read_value(self, index, prop):
        reg = self.regs[prop]
        register_type, slave, register, scale, offset = self.reg_basic_info(reg, index)
        count = reg.get(CONF_COUNT, 1)
        if register_type == REGISTER_TYPE_COIL:
            result = await self.hub.async_pb_call(slave, register, count, CALL_TYPE_COIL)
            return bool(result.bits[0])
        if register_type == REGISTER_TYPE_INPUT:
            result = await self.hub.async_pb_call(slave, register, count, CALL_TYPE_REGISTER_INPUT)
        else:
            result = await self.hub.async_pb_call(slave, register, count, CALL_TYPE_REGISTER_HOLDING)
        val = 0
        registers = result.registers
        if reg.get(CONF_REVERSE_ORDER):
            registers.reverse()
        byte_string = b''.join([x.to_bytes(2, byteorder='big') for x in registers])
        val = struct.unpack(reg[CONF_STRUCTURE], byte_string)[0]
        value = scale * val + offset
        # _LOGGER.debug("Read %d: %s = %f at %s/slave%s/register%s", index, prop, value, register_type, slave, register)
        return value

    async def write_value(self, index, prop, value):
        """Set property value."""
        reg = self.regs[prop]
        register_type, slave, register, scale, offset = self.reg_basic_info(reg, index)
        if register_type == REGISTER_TYPE_COIL:
            await self.hub.async_pb_call(slave, register, bool(value), CALL_TYPE_WRITE_COIL)
        else:
            val = (value - offset) / scale
            await self.hub.async_pb_call(slave, register, int(val), CALL_TYPE_WRITE_REGISTER)


class MyModbusClimate(ClimateEntity):
    """Representation of a Modbus climate device."""

    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, bus, name, index=-1):
        """Initialize the climate device."""
        self._bus = bus
        self._name = name
        self._index = index
        self._values = {}
        self._last_on_operation = None
        self._skip_update = False
        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        for prop in self._bus.regs:
            features |= SUPPORTED_FEATURES[prop]
        self._attr_supported_features = features

    @property
    def unique_id(self):
        from homeassistant.util import slugify
        return self.__class__.__name__.lower() + '.' + slugify(self.name)

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._bus.unit

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.get_value(REG_TEMPERATURE)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.get_value(REG_TARGET_TEMPERATURE)

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self.get_value(REG_HUMIDITY)

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self.get_value(REG_TARGET_HUMIDITY)

    @property
    def hvac_action(self):
        """Return current operation ie. heat, cool, idle."""
        return HVAC_ACTIONS[self.hvac_mode]

    @property
    def hvac_mode(self):
        if REG_HVAC_ON_OFF in self._bus.regs:
            if self.get_value(REG_HVAC_ON_OFF) == self._bus.hvac_off_value:
                return HVACMode.OFF
        hvac_mode = self.get_mode(self._bus.hvac_modes, REG_HVAC_MODE) or HVACMode.OFF
        if hvac_mode != HVACMode.OFF:
            self._last_on_operation = hvac_mode
        return hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return list(self._bus.hvac_modes)

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.get_mode(self._bus.fan_modes, REG_FAN_MODE)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return list(self._bus.fan_modes)

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return self.get_mode(self._bus.swing_modes, REG_SWING_MODE)

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return list(self._bus.swing_modes)

    @property
    def preset_mode(self):
        """Return preset mode setting."""
        return self.get_value(REG_PRESET_MODE)

    @property
    def preset_modes(self):
        """List of available swing modes."""
        return list(self._bus.preset_modes)

    @property
    def is_aux_heat(self):
        """Return true if aux heat is on."""
        return self.get_value(REG_AUX_HEAT) == self._bus.aux_heat_on_value

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self.set_value(REG_TARGET_TEMPERATURE_SET, temperature)

        # hvac_mode = kwargs.get('hvac_mode')
        # if hvac_mode is not None:
        #     self.set_hvac_mode(hvac_mode)

    async def async_set_humidity(self, humidity):
        """Set new target humidity."""
        await self.set_value(REG_TARGET_HUMIDITY, humidity)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        if REG_HVAC_ON_OFF in self._bus.regs:
            await self.set_value(REG_HVAC_ON_OFF_SET, self._bus.hvac_off_value if hvac_mode == HVACMode.OFF else self._bus.hvac_on_value)
            if hvac_mode == HVACMode.OFF:
                return

        if hvac_mode not in self._bus.hvac_modes:  # Support HomeKit Auto Mode
            best_hvac_mode = self.best_hvac_mode
            _LOGGER.warn("Fix operation mode from %s to %s", hvac_mode, best_hvac_mode)
            hvac_mode = best_hvac_mode
            # current = self.current_temperature
            # target = self.target_temperature
            # hvac_mode = HVACMode.HEAT if current and target and current < target else HVACMode.COOL
        if hvac_mode is not None:
            await self.set_mode(self._bus.hvac_modes, REG_HVAC_MODE_SET, hvac_mode)

    @property
    def best_hvac_mode(self):
        for mode in (HVACMode.HEAT_COOL, HVACMode.COOL, HVACMode.HEAT):
            if mode in self._bus.hvac_modes:
                return mode
        return None

    async def async_turn_on(self):
        """Turn on."""
        _LOGGER.debug("Turn on")
        await self.async_set_hvac_mode(self._last_on_operation or self.best_hvac_mode)

    async def async_turn_off(self):
        """Turn off."""
        _LOGGER.debug("Turn off")
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        await self.set_mode(self._bus.fan_modes, REG_FAN_MODE_SET, fan_mode)

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        await self.set_mode(self._bus.swing_modes, REG_SWING_MODE, swing_mode)

    async def async_set_preset_mode(self, preset_mode):
        """Set new hold mode."""
        await self.set_value(REG_PRESET_MODE, preset_mode)

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        await self.set_value(REG_AUX_HEAT, self._bus.aux_heat_on_value)

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        await self.set_value(REG_AUX_HEAT, self._bus.aux_heat_off_value)

    async def async_update(self):
        """Update state."""
        if self._skip_update:
            self._skip_update = False
            _LOGGER.debug("Skip update on %s", self._name)
            return

        # _LOGGER.debug("Update on %s", self._name)
        for prop in self._bus.regs:
            try:
                self._values[prop] = await self._bus.read_value(self._index, prop)
            except:
                self._attr_available = False
                self._bus.exception()
                _LOGGER.debug("Exception %d on %s/%s", self._bus.error, self._name, prop)
                return
        self._bus.error = 0
        self._attr_available = True

    def get_value(self, prop):
        """Get property value."""
        return self._values.get(prop)

    async def set_value(self, prop, value):
        """Set property value."""
        _LOGGER.debug("Write %s: %s = %f", self.name, prop, value)
        self._skip_update = True
        await self._bus.write_value(self._index, prop, value)
        self._values[prop] = value
        # self.schedule_update_ha_state()

    def get_mode(self, modes, prop):
        value = self.get_value(prop)
        if value is not None:
            for k, v in modes.items():
                if v == value:
                    # _LOGGER.debug("get_mode: %s for %s", k, prop)
                    return k
        _LOGGER.error("Invalid value %s for %s/%s", value, self._name, prop)
        return None

    async def set_mode(self, modes, prop, mode):
        if mode in modes:
            await self.set_value(prop, modes[mode])
            return
        _LOGGER.error("Invalid mode %s for %s/%s", mode, self._name, prop)
