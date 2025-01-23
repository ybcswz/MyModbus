# [https://github.com/ybcswz/MyModbus](https://github.com/ybcswz/MyModbus)

Hitachi ModBus Climate Component for HomeAssistant

ModBus 空调插件，支持海信日立 ModBus 协议的空调，测试用的modbus适配器型号为：海信 HCPC-H2M4C。

原始地址：https://github.com/Yonsm/ZhiModBus
因为日立空调状态位和控制位是分开的，Yonsm大大的组件没办法直接用，就偷过来改了一下，感谢Yonsm大大，虽未谋面但久仰大名，二十多年前从wince时代的cele系列就开始用他的作品了

## 1. 安装准备

把 `mymodbus` 放入 `custom_components`；也支持在 [HACS](https://hacs.xyz/) 中添加自定义库的方式安装。

## 2. 我的配置


```yaml
modbus:
  - name: Hitachi
    type: tcp
    host: 192.168.100.4
    port: 502
    message_wait_milliseconds: 500

    climates:
      - platform: mymodbus
        hub: Hitachi
        name: [Room1, Room2, Room3, Room4, Room5]
        hvac_onoff: { registers: [40078, 40169, 40260, 40351, 40442] }
        hvac_mode: { registers: [40029, 40120, 40211, 40302, 40393] }
        hvac_mode_set: { registers: [40079, 40170, 40261, 40352, 40443] }
        hvac_modes: { auto: 1, cool: 2, dry: 4, fan_only: 8, heat: 10 }
        fan_mode: { registers: [40030, 40121, 40212, 40303, 40394] }
        fan_mode_set: { registers: [40080, 40171, 40262, 40353, 40444] }
        fan_modes: { 自动: 0, 高风: 2, 中风: 4, 低风: 8 }
        target_temperature: { registers: [40031, 40122, 40213, 40304, 40395] }
        target_temperature_set: { registers: [40081, 40172, 40263, 40354, 40445] }
        temperature: { registers: [40039, 40130, 40221, 40312, 40403] }
        temp_step: 1
        max_temp: 30
        min_temp: 19
```

