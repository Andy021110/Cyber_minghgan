/*
 * electron/main.js — 桌宠主进程（Mac 优先，Windows 后续）
 *
 * 桌宠的本质：一个被"伪装"过的窗口。
 *   transparent  → 背景透明，只显示角色
 *   frame:false  → 去掉边框标题栏
 *   alwaysOnTop  → 永远在最上层
 *   skipTaskbar  → 不进任务栏
 *   setIgnoreMouseEvents → 鼠标穿透（不挡你干活）
 *
 * 三个不做就不是桌宠的细节：
 *   1. 穿透与可点的矛盾 —— 鼠标移入时取消穿透，移开恢复（见 pet:hover）
 *   2. macOS 多桌面 —— setVisibleOnAllWorkspaces，否则切 Space 就消失
 *   3. 托盘图标 —— 没有它你退不掉这个程序
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, screen, shell } = require('electron');
const path = require('path');

let pet = null;
let main = null;
let tray = null;

const PET_HTML = path.join(__dirname, '../src/pet/index.html');
const TRAY_ICON = path.join(__dirname, '../src/pet/assets/tray.png');

// 后端地址：先用本地，后面可指向 47.76.25.13
const BACKEND = process.env.CYBER_BACKEND || 'http://127.0.0.1:8000';

function createPet() {
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;

  pet = new BrowserWindow({
    width: 96,
    height: 96,
    x: sw - 160,
    y: sh - 160,
    transparent: true,
    frame: false,
    resizable: false,
    movable: true,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    focusable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  pet.loadFile(PET_HTML);
  pet.setIgnoreMouseEvents(true, { forward: true });   // 默认穿透，不挡干活

  // macOS：所有桌面空间可见，否则切换 Space 就找不到它了
  if (process.platform === 'darwin') {
    pet.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    app.dock?.hide();                                   // 隐藏 Dock 图标，靠托盘管理
  }

  pet.on('closed', () => { pet = null; });
}

function createMainWindow() {
  if (main && !main.isDestroyed()) {
    main.show();
    main.focus();
    return;
  }
  main = new BrowserWindow({
    width: 1180,
    height: 760,
    title: '赛博明翰',
    webPreferences: { nodeIntegration: false },
  });
  // 阶段 0：主界面还没重做，先加载现有前端；重做后改指向新页面
  main.loadURL(process.env.CYBER_FRONTEND || 'http://127.0.0.1:5173');
  main.on('closed', () => { main = null; });
}

function createTray() {
  tray = new Tray(TRAY_ICON);
  const menu = Menu.buildFromTemplate([
    { label: '打开主界面', click: createMainWindow },
    { type: 'separator' },
    { label: '显示 / 隐藏桌宠', click: () => (pet.isVisible() ? pet.hide() : pet.show()) },
    { type: 'separator' },
    { label: '退出', click: () => { app.exit(0); } },
  ]);
  tray.setToolTip('赛博明翰');
  tray.setContextMenu(menu);
}

/* ── 与渲染进程协作 ───────────────────────────────────── */

// 桌宠尺寸随形象变化，渲染进程算好后告诉主进程
ipcMain.on('pet:ready', (_e, { w, h }) => {
  if (!pet) return;
  pet.setSize(Math.ceil(w), Math.ceil(h));
});

// 鼠标移入 → 取消穿透（可以点）；移开 → 恢复穿透（不挡干活）
ipcMain.on('pet:hover', (_e, inside) => {
  if (!pet) return;
  pet.setIgnoreMouseEvents(!inside, { forward: true });
});

ipcMain.on('pet:click', () => createMainWindow());

/* ── 生命周期 ─────────────────────────────────────────── */

app.whenReady().then(() => {
  createPet();
  createTray();
});

app.on('window-all-closed', () => {
  // 桌宠不该因为主界面关掉就退出——它是常驻的
  // 只有托盘里点"退出"才真正结束
});
