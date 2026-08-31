# 板2 上位机/固件 AT 契约

上位机视角的板2 串口契约，与固件仓
`stem-hub-board2/docs/board2-at-uart-pwm.md` 保持同步。
如固件协议变更，先改固件文档，再同步本文件与 `at_protocol.py` / `fake_firmware.py`。

## 物理层

- UART1（上位机链路）、UART2、UART3 均为 **9600 8N1，无硬件流控**
- 9600 8N1 一个字符时间约 1.04 ms（`+++` 保护时间判定基础）

## 帧格式

- AT 命令：**全大写**、无空格/制表符、以 `\r\n` 结尾，长度 ≤127 字节
- 成功响应：`OK\r\n`
- 错误响应：`+ERROR:<CODE>\r\n`（注意 `+` 前缀）
- 查询响应：数据行 + `OK\r\n` 两行
- AT 模式只解析 CRLF 帧，不做普通数据转发

## 命令集

| 命令 | 说明 | 失败码 |
| --- | --- | --- |
| `AT+12V=ON` / `OFF` | 12V Buck（PB12，低电平开启） | — |
| `AT+18V=ON` / `OFF` | 18V Buck（PB3，低电平开启） | — |
| `AT+NMOS1=ON` / `OFF` | NMOS1（PB4，高有效） | `12V_DISABLED` |
| `AT+NMOS2=ON` / `OFF` | NMOS2（PB15） | `12V_DISABLED` |
| `AT+NMOS3=ON` / `OFF` | NMOS3（PB6） | `12V_DISABLED` |
| `AT+PWM=<0..100>` | PWM 占空比百分比（PB9/TIM4_CH4，25 kHz） | `18V_DISABLED` `BREATH_ACTIVE` `RANGE` |
| `AT+PWM_TIME=<0..10000>` | 渐变时间 ms，掉电保存 | `RANGE` `STORAGE` |
| `AT+BREATH_TEST=ON` / `OFF` | 呼吸灯演示 | `18V_DISABLED` |
| `AT+STATUS=?` | 查询全部软件状态 | — |
| `AT+TRANS=1` / `2` / `1&2` | 进入 UART1→UART2 / UART3 / 双目标透明模式 | `PARSE` |
| `AT+UARTTX=<HEX>` | 兼容保留；AT 模式下固定返回 `UART_DISABLED` | `UART_DISABLED` `RANGE` |

## 状态回读

`AT+STATUS=?` →

```text
+STATUS:12V=OFF,18V=OFF,NMOS1=OFF,NMOS2=OFF,NMOS3=OFF,PWM=0,PWM_TARGET=0,PWM_TIME=500,BREATH=OFF
OK
```

- 字段顺序与键名固定，上位机解析器要求完整键集合（`models.StatusState`）
- `PWM` 是当前感知亮度，`PWM_TARGET` 是目标；固件每 10 ms 非阻塞推进渐变
- 上位机握手即 `AT+STATUS=?`：5 秒内收到完整 `+STATUS` + `OK` 视为连接成功

## 错误码全表

| 错误码 | 含义 | 上位机行为 |
| --- | --- | --- |
| `PARSE` | 未知命令/格式错误/非法字符 | AT 终端提示 |
| `RANGE` | PWM > 100 或 HEX > 32 字节 | 输入端预校验 + 提示 |
| `UART_DISABLED` | AT 模式下无活动透传目标 | 仅 raw 命令可见 |
| `UART_TX` | 固件 HAL 发送失败/超时 | 错误提示 |
| `LINE_TOO_LONG` | 输入帧 > 127 字节 | 错误提示 |
| `RX_OVERFLOW` | 固件环形缓冲溢出 | 错误提示 |
| `12V_DISABLED` | 12V 未开时尝试开 NMOS | UI 预禁用 NMOS |
| `18V_DISABLED` | 18V 未开时 PWM 非 0 / 开呼吸灯 | UI 预禁用 PWM |
| `BREATH_ACTIVE` | 呼吸灯期间普通 PWM 命令 | 错误提示 |
| `STORAGE` | 渐变时间写 Flash 失败 | 错误提示 |

## 联锁规则（上位机 UI 同步实现）

1. 12V 关闭时 NMOS 不能开启（固件拒绝 + UI 预禁用）
2. 关闭 12V 自动关闭三路 NMOS
3. 18V 关闭时 PWM 只能设为 0（固件拒绝 + UI 预禁用）
4. 关闭 18V 自动清零 PWM 并停止呼吸灯演示
5. 呼吸灯演示期间普通 PWM 命令被拒；关 18V 始终立即停演示

UI 的开关位置一律以 `+STATUS` 回读为准（约 1 Hz 轮询 + 命令成功后补查）。

## 透明模式

- `AT+TRANS=x` 返回 `OK\r\n` 后进入；此后 UART1 所有字节（含形似 AT 的字符串、
  `0x00`、CRLF）都原样转发到目标，不经过 AT 解析
- 下游 UART2/UART3 收到的数据以大写 HEX 事件回传 UART1，单事件 ≤32 字节：
  `+UART2RX:<HEX>\r\n` / `+UART3RX:<HEX>\r\n`
- 退出：发送前后各静默 ≥1 ms 的 `+++`（裸字节，不带 CRLF），固件消耗后返回 `OK\r\n`
  - 不满足保护时间的 `+++`、`abc+++def`、`++++` 全部原样转发
  - 上位机实现：发送用户数据后延时 30 ms 再发 `+++`，然后等待 `OK`（1 s 超时）
  - 退出成功后固件清空 UART2/3 待回传数据并清除目标
- 透传期间上位机暂停 `AT+STATUS=?` 轮询；进入透传的确认 OK 之后不得再发任何
  AT 查询（否则会作为 payload 转发到下游）

## 上位机发送约束

- 控制/查询命令单条发送、等待回包后发送下一条（worker FIFO 保证）
- 透传发送为裸字节直写，不做 32 字节分帧（分帧是固件下行事件的职责）
- 任何非 `OK` / `+ERROR:` / `+STATUS:` / `+UARTxRX:` 的行按协议违规丢弃并告警
