// Мост рендерер → главный процесс: пробрасываем строку таймера в меню-бар macOS.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('focusboardShell', {
  // state — объект состояния таймера или null (покой). Форматирует и рисует значок main.
  timerUpdate: (state) => ipcRenderer.send('timer-update', state ?? null),
});
