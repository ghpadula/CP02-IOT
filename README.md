# Smart Gym Station — CP02
**FIAP · Engenharia de Software · Physical Computing (IoT & IoB)**

> Sistema de estação inteligente de treino com identificação via RFID, persistência SQLite, monitoramento por câmera (MediaPipe) e interface gráfica (Tkinter).

---

## Equipe

| Nome | RM |
|------|----|
| Gabriel Henrique Padula| RM 554907 |
| Arthur Abonizio | RM 555506  |
| Rodrigo Nakata| RM 556417  |

---

## 📐 Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     SMART GYM STATION                       │
│                                                             │
│  [Arduino/ESP32]──Serial──▶ [Python]                        │
│   └─ Leitor RFID (RC522)    ├─ SQLite (smart_gym.db)        │
│                             ├─ MediaPipe (câmera/esqueleto) │
│                             └─ Tkinter (IHM/GUI)            │
└─────────────────────────────────────────────────────────────┘
```

---

## Banco de Dados (SQLite)

### Tabela `alunos`
| Coluna       | Tipo    | Descrição                          |
|--------------|---------|------------------------------------|
| id           | INTEGER | Chave primária (autoincremento)     |
| nome         | TEXT    | Nome completo do aluno             |
| uid_rfid     | TEXT    | UID único do cartão RFID           |
| exercicio    | TEXT    | Exercício prescrito                |
| repeticoes   | INTEGER | Número de repetições da meta       |

### Tabela `log_acessos`
| Coluna    | Tipo    | Descrição                                   |
|-----------|---------|---------------------------------------------|
| id        | INTEGER | Chave primária (autoincremento)              |
| aluno_id  | INTEGER | FK → alunos.id                              |
| uid_rfid  | TEXT    | UID do cartão utilizado                     |
| horario   | TEXT    | Timestamp do acesso (`datetime localtime`)  |

---

## Hardware

| Componente           | Quantidade | Observação                   |
|----------------------|------------|------------------------------|
| ESP32 (ou Arduino)   | 1          | Microcontrolador principal   |
| Módulo RFID RC522    | 1          | Leitura de cartões/tags      |
| Cartão/Tag RFID      | 1+         | Um por aluno cadastrado      |
| Câmera USB           | 1          | Para detecção de pose        |
| Cabos jumper         | —          | Conexão RFID → ESP32         |

### Diagrama de Conexões (ESP32 + RC522)

```
RC522  →  ESP32
------    -----
SDA    →  GPIO 5   (SS)
SCK    →  GPIO 18
MOSI   →  GPIO 23
MISO   →  GPIO 19
IRQ    →  (não conectado)
GND    →  GND
RST    →  GPIO 22
3.3V   →  3.3V
```

---

## Bibliotecas

### Python
```
tkinter       # GUI (nativa)
sqlite3       # Banco de dados (nativa)
pyserial      # Comunicação serial com Arduino/ESP32
opencv-python # Captura de câmera
mediapipe     # Detecção de pose / esqueleto
Pillow        # Renderização de frames no Tkinter
```

### Arduino/ESP32
```
MFRC522       # Leitura do módulo RFID RC522
SPI           # Protocolo de comunicação (nativa)
```

---

## Setup e Execução

### 1. Clonar o repositório
```bash
git clone https://github.com/<seu-usuario>/smart-gym-cp02.git
cd smart-gym-cp02
```

### 2. Instalar dependências Python
```bash
pip install opencv-python mediapipe pyserial Pillow
```

### 3. Criar e popular o banco de dados
```bash
python setup_db.py
```
Isso cria `smart_gym.db` com 5 alunos de exemplo.  
Para adicionar alunos reais, edite o array `alunos_iniciais` em `setup_db.py` com os UIDs reais dos cartões.

### 4. Configurar a porta serial
Edite `smart_gym.py` (linha ~20):
```python
SERIAL_PORT = "COM3"        # Windows
# SERIAL_PORT = "/dev/ttyUSB0"  # Linux
# SERIAL_PORT = "/dev/cu.usbserial-..."  # macOS
```

### 5. Gravar firmware no Arduino/ESP32
Abra `firmware/rfid_reader.ino` na Arduino IDE e grave na placa.

### 6. Executar a aplicação

**Com hardware físico (RFID + câmera):**
```bash
python smart_gym.py
```

**Modo demo (sem hardware — ideal para testes):**
```bash
python smart_gym_demo.py
```

---

## Fluxo de Uso

```
Aproximar cartão RFID
        ↓
ESP32 lê o UID e envia via Serial
        ↓
Python recebe o UID
        ↓
Consulta SQLite → aluno encontrado?
   Sim → registra log + ativa interface
   Não → exibe alerta de UID inválido
        ↓
Tkinter exibe boas-vindas + exercício + meta
        ↓
Câmera liga → MediaPipe detecta esqueleto
        ↓
Repetições são contadas automaticamente
        ↓
Aluno pressiona "Encerrar Sessão"
```

---

## Vídeo Demonstrativo

🔗 _(Inserir link do vídeo aqui)_

---

## Estrutura do Repositório

```
smart-gym-cp02/
├── setup_db.py          # Cria e popula o banco de dados
├── smart_gym.py         # Aplicação principal (com RFID físico)
├── smart_gym_demo.py    # Modo demo (sem hardware)
├── smart_gym.db         # Banco de dados SQLite (gerado pelo setup)
├── firmware/
│   └── rfid_reader.ino  # Código Arduino/ESP32
└── README.md
```
