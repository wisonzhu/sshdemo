<template>
  <div class="ssh-panel" :class="{ fullscreen: isFullscreen }">
    <!-- 左侧主机管理面板 -->
    <div class="host-panel" :style="{ width: panelWidth + 'px' }" @mousedown="startDrag">
      <el-card class="host-card" shadow="hover">
        <div slot="header" class="card-header">
          <span class="header-title">Host Management</span>
          <el-tooltip content="Add New Host" placement="top">
            <el-button
              type="primary"
              icon="el-icon-plus"
              size="mini"
              @click="showAddHostDialog"
              circle
            />
          </el-tooltip>
        </div>
        <el-scrollbar style="height: calc(100vh - 150px)">
          <el-menu
            :default-active="currentHost"
            class="host-menu"
            @select="switchHost"
            background-color="#fff"
            text-color="#606266"
            active-text-color="#409EFF"
          >
            <el-menu-item
              v-for="host in hostList"
              :key="host.id"
              :index="host.id.toString()"
              class="host-item"
            >
              <i class="el-icon-monitor"></i>
              <span>{{ host.name }}</span>
              <el-tooltip content="Remove Host" placement="top">
                <el-button
                  type="danger"
                  size="mini"
                  icon="el-icon-delete"
                  circle
                  @click.stop="removeHost(host.id)"
                  class="delete-btn"
                />
              </el-tooltip>
            </el-menu-item>
          </el-menu>
        </el-scrollbar>
      </el-card>
    </div>

    <!-- 右侧终端区域 -->
    <div class="terminal-panel">
      <el-card class="terminal-card" shadow="hover">
        <div slot="header" class="card-header">
          <span class="header-title">Terminal - {{ currentHostName }}</span>
          <el-tooltip content="Toggle Fullscreen" placement="top">
            <el-button
              type="primary"
              :icon="isFullscreen ? 'el-icon-copy-document' : 'el-icon-full-screen'"
              @click="toggleFullscreen"
              size="small"
            />
          </el-tooltip>
          <el-button
            type="warning"
            size="small"
            icon="el-icon-refresh"
            @click="clearTerminal"
            style="margin-left: 10px"
          >
            Clear
          </el-button>
        </div>
        <div class="terminal-wrapper" v-show="isConnected">
          <div class="terminal-container" ref="terminal">
            <div class="terminal-content"></div>
          </div>
        </div>
        <el-alert
          v-if="!isConnected"
          :title="statusMessage"
          type="warning"
          :closable="false"
          show-icon
          class="status"
        />
        <el-alert
          v-else
          :title="statusMessage"
          type="success"
          :closable="false"
          show-icon
          class="status"
        />
      </el-card>
    </div>

    <!-- 添加主机对话框 -->
    <el-dialog
      :visible.sync="addHostDialogVisible"
      title="Add New Host"
      width="30%"
      :before-close="closeAddHostDialog"
      custom-class="connection-dialog"
    >
      <el-form :model="newHost" label-width="80px" size="small" ref="hostForm" @submit.native.prevent>
        <el-form-item label="Name" prop="name" :rules="[{ required: true, message: 'Please input name' }]">
          <el-input v-model="newHost.name" placeholder="Enter host name"></el-input>
        </el-form-item>
        <el-form-item label="Host" prop="host" :rules="[{ required: true, message: 'Please input host' }]">
          <el-input v-model="newHost.host" placeholder="Enter host"></el-input>
        </el-form-item>
        <el-form-item label="Username" prop="username" :rules="[{ required: true, message: 'Please input username' }]">
          <el-input v-model="newHost.username" placeholder="Enter username"></el-input>
        </el-form-item>
        <el-form-item label="Password" prop="password" :rules="[{ required: true, message: 'Please input password' }]">
          <el-input
            v-model="newHost.password"
            type="password"
            placeholder="Enter password"
            show-password
          ></el-input>
        </el-form-item>
        <el-form-item label="Port" prop="port">
          <el-input v-model.number="newHost.port" placeholder="22" type="number"></el-input>
        </el-form-item>
      </el-form>
      <span slot="footer" class="dialog-footer">
        <el-button @click="closeAddHostDialog">Cancel</el-button>
        <el-button type="primary" @click="addHost">Add</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";

export default {
  name: "SshTerminal",
  props: {
    host: { type: String, default: "" },
    username: { type: String, default: "" },
    password: { type: String, default: "" },
    port: { type: Number, default: 22 },
  },
  data() {
    return {
      panelWidth: 300,
      form: { host: this.host, username: this.username, password: this.password, port: this.port },
      newHost: { id: Date.now(), name: "", host: "", username: "", password: "", port: 22 },
      hostList: [],
      currentHost: null,
      currentHostName: "Not Connected",
      isConnected: false,
      statusMessage: "Disconnected",
      terminal: null,
      fitAddon: null,
      socket: null,
      isFullscreen: false,
      addHostDialogVisible: false,
      isDragging: false,
      dragStartX: 0,
    };
  },
  watch: {
    isConnected(newVal) {
      if (newVal && this.currentHost === null && this.hostList.length > 0) {
        this.currentHost = this.hostList[0].id;
        this.switchHost(this.currentHost.toString());
      }
    },
  },
  beforeDestroy() {
    this.disconnect();
    if (window && window.removeEventListener) {
      window.removeEventListener("resize", this.adjustTerminalSize);
      document.removeEventListener("mousemove", this.onDrag);
      document.removeEventListener("mouseup", this.stopDrag);
    }
  },
  mounted() {
    if (this.isConfigured) {
      this.hostList.push({ id: Date.now(), name: "Default", ...this.form });
      this.currentHost = this.hostList[0].id;
      this.currentHostName = "Default";
      this.connect();
    }
    const resizer = this.$el.querySelector(".host-panel");
    resizer.addEventListener("mousedown", this.startDrag);
  },
  methods: {
    connect() {
      const host = this.form.host;
      const username = this.form.username;
      const password = this.form.password;
      const port = this.form.port;
      if (!host || !username || !password) {
        this.statusMessage = "Please fill in all fields";
        return;
      }

      this.isDialogVisible = false;
      try {
        this.statusMessage = "Connecting...";

        if (this.terminal) {
          this.terminal.dispose();
          this.terminal = null;
          this.fitAddon = null;
        }

        this.terminal = new Terminal({
          cursorBlink: true,
          theme: { background: "#1e1e1e", foreground: "#ffffff" },
          scrollback: 10000,
          scrollSensitivity: 50,
        });
        this.fitAddon = new FitAddon();
        this.terminal.loadAddon(this.fitAddon);
        if (this.$refs.terminal) {
          this.terminal.open(this.$refs.terminal.querySelector(".terminal-content"));
          this.fitAddon.fit();
        }

        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        this.socket = new WebSocket(
          `${protocol}://localhost:8000/ssh?host=${host}&port=${port}&username=${username}&password=${password}`
        );

        this.socket.onopen = () => {
          this.isConnected = true;
          this.statusMessage = "Connected";
          if (this.terminal) {
            this.terminal.write(`Connected to ${host}\r\n`);
            this.$nextTick(() => this.adjustTerminalSize());
          }
        };

        this.socket.onmessage = (event) => {
          if (this.terminal) {
            this.terminal.write(event.data);
            this.$nextTick(() => this.adjustTerminalSize());
          }
        };

        this.socket.onerror = (error) => {
          this.statusMessage = "Connection error";
          if (this.terminal) this.terminal.write("Connection error\r\n");
          console.error("WebSocket error:", error);
        };

        this.socket.onclose = () => {
          this.isConnected = false;
          this.statusMessage = "Disconnected";
          if (this.terminal) this.terminal.write("\r\nConnection closed\r\n");
        };

        this.terminal.onData((data) => {
          if (this.socket && this.socket.readyState === WebSocket.OPEN) this.socket.send(data);
        });

        if (window && window.addEventListener) window.addEventListener("resize", this.adjustTerminalSize);
      } catch (error) {
        this.statusMessage = "Failed to initialize terminal";
        console.error("Terminal initialization error:", error);
      }
    },
    disconnect() {
      if (this.socket) this.socket.close();
      if (this.terminal) {
        this.terminal.dispose();
        this.terminal = null;
        this.fitAddon = null;
      }
      this.isConnected = false;
      this.statusMessage = "Disconnected";
      this.isFullscreen = false;
    },
    toggleFullscreen() {
      this.isFullscreen = !this.isFullscreen;
      this.$nextTick(() => setTimeout(() => this.adjustTerminalSize(), 200));
    },
    adjustTerminalSize() {
      if (this.terminal && this.$refs.terminal && this.fitAddon) {
        const container = this.$refs.terminal;
        const card = this.$el.querySelector(".terminal-card");
        const containerHeight = container.offsetHeight;
        const cardHeight = card ? card.offsetHeight : 0;
        const windowHeight = window.innerHeight;
        const cardHeaderHeight = this.$el.querySelector(".terminal-card .card-header")
          ? this.$el.querySelector(".terminal-card .card-header").offsetHeight
          : 0;
        const statusHeight = this.$el.querySelector(".status") ? this.$el.querySelector(".status").offsetHeight : 0;
        const expectedHeight = this.isFullscreen
          ? windowHeight - cardHeaderHeight - statusHeight - 10 // 全屏时填满，减去边距
          : cardHeight * 0.8 - cardHeaderHeight - statusHeight; // 非全屏调整为80%高度

        if (container) {
          container.style.height = `${expectedHeight}px`;
          container.style.minHeight = `${expectedHeight}px`;
          container.style.maxHeight = `${expectedHeight}px`;
          container.style.overflow = "auto";
          container.style.boxSizing = "border-box";
        }

        this.fitAddon.fit();
        this.terminal.scrollToBottom();

        console.log(
          "Terminal height adjusted, container height:",
          container.offsetHeight,
          "card height:",
          cardHeight,
          "window height:",
          windowHeight,
          "card header height:",
          cardHeaderHeight,
          "status height:",
          statusHeight,
          "expected height:",
          expectedHeight,
          "viewport rows:",
          this.terminal.rows
        );
      }
    },
    showAddHostDialog() {
      this.newHost = { id: Date.now(), name: "", host: "", username: "", password: "", port: 22 };
      this.addHostDialogVisible = true;
    },
    closeAddHostDialog() {
      this.addHostDialogVisible = false;
      this.$refs.hostForm.resetFields();
    },
    addHost() {
      this.$refs.hostForm.validate((valid) => {
        if (valid) {
          this.hostList.push({ ...this.newHost });
          this.closeAddHostDialog();
          if (!this.isConnected && this.hostList.length === 1) {
            this.currentHost = this.newHost.id;
            this.form = { ...this.newHost };
            this.connect();
          }
        }
      });
    },
    removeHost(hostId) {
      this.hostList = this.hostList.filter((h) => h.id !== hostId);
      if (this.currentHost === hostId) {
        this.disconnect();
        if (this.hostList.length > 0) {
          this.currentHost = this.hostList[0].id;
          this.switchHost(this.currentHost.toString());
        } else {
          this.currentHost = null;
          this.currentHostName = "Not Connected";
        }
      }
    },
    switchHost(hostId) {
      const host = this.hostList.find((h) => h.id.toString() === hostId);
      if (host) {
        this.disconnect();
        this.currentHost = host.id;
        this.currentHostName = host.name;
        this.form = { ...host };
        this.$nextTick(() => this.connect());
      }
    },
    clearTerminal() {
      if (this.terminal) {
        this.terminal.clear();
        this.terminal.write("Terminal cleared\r\n");
      }
    },
    startDrag(event) {
      this.isDragging = true;
      this.dragStartX = event.pageX;
      document.addEventListener("mousemove", this.onDrag);
      document.addEventListener("mouseup", this.stopDrag);
    },
    onDrag(event) {
      if (this.isDragging) {
        const diffX = event.pageX - this.dragStartX;
        this.panelWidth = Math.max(200, Math.min(400, this.panelWidth - diffX));
        this.dragStartX = event.pageX;
        this.adjustTerminalSize();
      }
    },
    stopDrag() {
      this.isDragging = false;
      document.removeEventListener("mousemove", this.onDrag);
      document.removeEventListener("mouseup", this.stopDrag);
    },
  },
};
</script>

<style scoped>
.ssh-panel {
  display: flex;
  height: 80vh;
  width: 100%;
  background-color: #F5F7FA;
  transition: all 0.3s ease-in-out;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  user-select: none;
}

.ssh-panel.fullscreen {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 4000 !important;
  padding: 0 !important;
  margin: 0 !important;
  animation: fadeIn 0.3s ease-in-out;
}

.host-panel {
  flex-shrink: 0;
  padding: 12px;
  background-color: #fff;
  border-right: 1px solid #E6E6E6;
  position: relative;
  cursor: col-resize;
  transition: width 0.3s ease-in-out;
}

.host-panel::after {
  content: "";
  position: absolute;
  right: -4px;
  top: 0;
  width: 8px;
  height: 100%;
  cursor: col-resize;
  background: linear-gradient(to right, transparent, #E6E6E6, transparent);
}

.host-panel.dragging::after {
  background: #409EFF;
}

.terminal-panel {
  flex: 1;
  padding: 12px;
}

.host-card,
.terminal-card {
  height: 100%;
  overflow: hidden;
  border-radius: 6px;
  background-color: #fff;
  color: #303133;
  border: 1px solid #E6E6E6;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease-in-out;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background-color: #F5F7FA;
  border-bottom: 1px solid #E6E6E6;
  transition: background-color 0.3s ease-in-out;
}

.card-header:hover {
  background-color: #E9ECEF;
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.host-menu {
  border-right: none;
}

.host-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px !important;
  transition: all 0.2s ease-in-out;
}

.host-item:hover {
  background-color: #F5F7FA !important;
}

.delete-btn {
  margin-left: 10px;
}

.terminal-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
  margin: 0;
  transition: all 0.3s ease-in-out;
}

.terminal-container {
  flex: 0.8; /* 提高至80%高度 */
  background-color: #1e1e1e;
  border-radius: 4px;
  overflow: auto !important;
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  border: 1px solid #E6E6E6;
  transition: height 0.3s ease-in-out;
}

.terminal-content {
  width: 100%;
  flex: 1;
  overflow-y: auto !important;
  box-sizing: border-box;
}

.status {
  margin: 12px 0;
  padding: 8px;
  border-radius: 4px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  background-color: #fff;
  color: #303133;
  transition: all 0.3s ease-in-out;
}

.ssh-panel.fullscreen .terminal-wrapper {
  height: calc(100vh - 60px); /* 全屏时填满，减去header和status */
}

.ssh-panel.fullscreen .terminal-container {
  border-radius: 0;
  height: 100%;
  flex: 1;
  max-height: calc(100vh - 60px); /* 限制最大高度 */
}

.ssh-panel.fullscreen,
.ssh-panel.fullscreen * {
  max-height: none !important;
  min-height: 0 !important;
  overflow: visible !important;
  box-sizing: border-box !important;
}

.ssh-panel.fullscreen {
  transform: translateZ(0);
  -webkit-transform: translateZ(0);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
