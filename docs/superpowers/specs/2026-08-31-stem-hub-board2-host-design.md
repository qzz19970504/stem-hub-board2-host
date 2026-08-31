# stem-hub-board2-host 上位机设计

日期: 2026-08-31
状态: 已确认（用户已选定全部推荐选项）

## 目标

为 `D:\Codes\STM32\stem-hub-board2` 固件（STM32F103C8 + FreeRTOS，UART1 AT 命令 +
UART2/UART3 透传）开发 PyQt 风格上位机：

- 界面风格参考 `D:\Codes\STM32\stem-hub-host`（深色控制台设计令牌 + QSS + 组件）
- GUI 绑定使用 PySide6（与参考工程一致，QtSerialPort 位于 PySide6-Addons）
- 两页布局: Tab1 控制台（电源/NMOS/PWM/呼吸灯/STATUS/AT 终端）、Tab2 透传
- 内置 `--fake` 模拟固件，无硬件可完整联调
- 打包为 `dist\stem-hub-board2-host.exe`
- 环境使用本机 miniconda（`C:\ProgramData\miniconda3`）新建 `stem-hub-board2-host`
- 保留完善文本: README、env/README、AT 契约文档、spec 注释、pytest 测试

## 架构（镜像参考工程）

```
stem_hub_board2_host/
├── main.py / app.py / branding.py
├── serial_worker.py   # 行切分 + 单发等回包 FIFO + 重同步
├── transport.py       # RealSerialTransport / FakeSerialTransport
├── at_protocol.py     # 命令构造 + ParsedResponse + LineSplitter
├── controller.py      # 握手(AT+STATUS?) + 命令编排 + 透传状态机 + 联锁
├── models.py          # AtError / StatusState / UartRxFrame
├── fake_firmware.py   # 模拟联锁/渐变 PWM/透传/+++ 退出
└── ui/
    ├── main_window.py / theme.py / style.qss / fonts.py / stylesheet.py / native_chrome.py
    ├── tab1_console.py / tab2_passthrough.py
    └── widgets/ (serial_bar, toggle_switch, at_console, passthrough_panel,
                  power_card, nmos_card, pwm_card, status_card, theme_toggle)
```

## 协议要点（源自固件 docs/board2-at-uart-pwm.md）

- UART1 9600 8N1；AT 命令全大写、无空格、CRLF 结尾
- 成功 `OK\r\n`；错误 `+ERROR:PARSE|RANGE|UART_DISABLED|UART_TX|LINE_TOO_LONG|
  RX_OVERFLOW|12V_DISABLED|18V_DISABLED|BREATH_ACTIVE|STORAGE\r\n`（注意 + 前缀）
- 查询 `AT+STATUS=?` → `+STATUS:12V=,18V=,NMOS1=,NMOS2=,NMOS3=,PWM=,PWM_TARGET=,
  PWM_TIME=,BREATH=` + `OK`
- 透传 `AT+TRANS=1|2|1&2` → OK 后进入；`+++`（前后 ≥1ms 静默）退出并回 OK
- 下行事件 `+UART2RX:<HEX>` / `+UART3RX:<HEX>`（≤32 字节/事件）
- 联锁: 12V 关 → NMOS 不能开；18V 关 → PWM 只能 0%；关 12V 自动关 NMOS，
  关 18V 自动清 PWM；呼吸灯开启时普通 PWM 命令被拒
- 握手: 固件无 AT+VERSION?，以 `AT+STATUS=?` 完整回包作为握手

## 关键决策

1. 握手与周期刷新都基于 `AT+STATUS=?`（1 Hz 轮询，透传期间暂停）
2. 透传发送走原始字节（`worker.send_bytes`），退出用 raw `+++` + 等待 OK；
   AT+UARTTX 在板2 AT 模式下固定返回 UART_DISABLED，不用于发送
3. UI 联锁为预判禁用，最终状态以 +STATUS 回读为准
4. 打包链路与参考工程一致: conda 开发环境 + `env\release` venv（Python 3.11）
   + 固定版本 requirements-release.txt + PyInstaller spec；打包后 --fake 冒烟验收

## 测试

pytest: at_protocol 解析、models 解析（STATUS/UARTxRX/ERROR）、controller
联锁与透传状态机（FakeSerialTransport 驱动）、fake_firmware 命令面。
UI 验收: `--fake` 启动 + 打包后冒烟。
