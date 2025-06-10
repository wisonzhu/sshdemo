<template>
  <div class="ssh-terminal" :class="{ fullscreen: isFullscreen }">
    <div class="control-panel">
      <button v-if="isConnected" @click="toggleFullscreen">{{ isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen' }}</button>
      <button v-if="isConnected" @click="disconnect">Disconnect</button>
    </div>
    <div class="connection-form" v-if="!isConnected">
      <h3>SSH Connection</h3>
      <div class="form-group">
        <label>Host:</label>
        <input v-model="host" placeholder="Enter host" />
      </div>
      <div class="form-group">
        <label>Username:</label>
        <input v-model="username" placeholder="Enter username" />
      </div>
      <div class="form-group">
        <label>Password:</label>
        <input type="password" v-model="password" placeholder="Enter password" />
      </div>
      <div class="form-group">
        <label>Port:</label>
        <input v-model="port" placeholder="22" type="number" />
      </div>
      <button @click="connect">Connect</button>
    </div>
    <div class="terminal-container" ref="terminal" v-show="isConnected">
      <div class="terminal-content"></div> <!-- 终端内容区域 -->
    </div>
    <div class="status" :class="{ connected: isConnected }">
      {{ statusMessage }}
    </div>
  </div>
</template>

<script>
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";

export default {
  name: "SshTerminal",
  data() {
    return {
      host: "",
      username: "",
      password: "",
      port: 22,
      isConnected: false,
      statusMessage: "Disconnected",
      terminal: null,
      socket: null,
      isFullscreen: false,
    };
  },
  beforeDestroy() {
    this.disconnect();
    window.removeEventListener("resize", this.fitTerminal);
  },
  methods: {
    async connect() {
      if (!this.host || !this.username || !this.password) {
        this.statusMessage = "Please fill in all fields";
        return;
      }

      try {
        this.statusMessage = "Connecting...";

        // Initialize xterm
        this.terminal = new Terminal({
          cursorBlink: true,
          theme: {
            background: "#1e1e1e",
            foreground: "#ffffff",
          },
          scrollback: 1000, // 增加滚动历史记录
        });
        const fitAddon = new FitAddon();
        this.terminal.loadAddon(fitAddon);
        this.terminal.open(this.$refs.terminal.querySelector(".terminal-content"));
        fitAddon.fit();

        // Initialize WebSocket for SSH
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        this.socket = new WebSocket(
          `${protocol}://localhost:8000/ssh?host=${this.host}&port=${this.port}&username=${this.username}&password=${this.password}`
        );

        this.socket.onopen = () => {
          this.isConnected = true;
          this.statusMessage = "Connected";
          this.terminal.write("Connected to " + this.host + "\r\n");
        };

        this.socket.onmessage = (event) => {
          this.terminal.write(event.data);
        };

        this.socket.onerror = (error) => {
          this.statusMessage = "Connection error";
          this.terminal.write("Connection error\r\n");
          console.error("WebSocket error:", error);
        };

        this.socket.onclose = () => {
          this.isConnected = false;
          this.statusMessage = "Disconnected";
          this.terminal.write("\r\nConnection closed\r\n");
        };

        // Handle terminal input
        this.terminal.onData((data) => {
          if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(data);
          }
        });

        // Handle window resize
        window.addEventListener("resize", () => {
          this.adjustTerminalSize();
        });
      } catch (error) {
        this.statusMessage = "Failed to initialize terminal";
        console.error("Terminal initialization error:", error);
      }
    },
    disconnect() {
      if (this.socket) {
        this.socket.close();
      }
      if (this.terminal) {
        this.terminal.dispose();
      }
      this.isConnected = false;
      this.statusMessage = "Disconnected";
      this.isFullscreen = false; // 断开连接时退出全屏
    },
    toggleFullscreen() {
      this.isFullscreen = !this.isFullscreen;
      this.$nextTick(() => {
        this.adjustTerminalSize();
      });
    },
    adjustTerminalSize() {
      if (this.terminal) {
        const fitAddon = this.terminal.getAddon("fit");
        fitAddon.fit();
        // 确保滚动条位于底部
        this.terminal.scrollToBottom();
      }
    },
  },
  watch: {
    isFullscreen(newVal) {
      if (newVal && this.terminal) {
        this.adjustTerminalSize();
      }
    },
  },
};
</script>

<style scoped>
.ssh-terminal {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  height: auto;
  transition: all 0.3s ease;
}

.ssh-terminal.fullscreen {
  padding: 0;
  max-width: none;
  margin: 0;
  width: 100vw;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1000;
}

.control-panel {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.control-panel button {
  padding: 5px 10px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.control-panel button:hover {
  background-color: #0056b3;
}

.connection-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.form-group label {
  width: 100px;
}

.form-group input {
  flex: 1;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

button {
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  width: fit-content;
}

button:hover {
  background-color: #0056b3;
}

.terminal-container {
  flex: 1;
  background-color: #1e1e1e;
  padding: 10px;
  border-radius: 4px;
  overflow: auto;
  position: relative;
  min-height: 200px; /* 确保有最小高度 */
}

.terminal-content {
  width: 100%;
  height: 100%;
}

.status {
  margin-top: 10px;
  padding: 8px;
  border-radius: 4px;
  background-color: #f8d7da;
  color: #721c24;
  text-align: center;
}

.ssh-terminal.fullscreen .terminal-container {
  border-radius: 0;
  height: calc(100vh - 60px); /* 留出空间给控制面板和状态栏 */
  display: flex;
  flex-direction: column;
}

.ssh-terminal.fullscreen .terminal-content {
  flex: 1;
}
</style>
