"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const child_process = __importStar(require("child_process"));
const path = __importStar(require("path"));
let serverProcess = null;
function activate(context) {
    startPythonServer(context);
    const provider = new MultiAgentChatViewProvider(context);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(MultiAgentChatViewProvider.viewType, provider));
    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand('multiAgent.startServer', () => {
        startPythonServer(context);
    }));
    context.subscriptions.push(vscode.commands.registerCommand('multiAgent.openState', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (workspaceFolders && workspaceFolders.length > 0) {
            const statePath = vscode.Uri.file(path.join(workspaceFolders[0].uri.fsPath, 'PROJECT_STATE.md'));
            try {
                const doc = await vscode.workspace.openTextDocument(statePath);
                await vscode.window.showTextDocument(doc);
            }
            catch (e) {
                vscode.window.showErrorMessage(`PROJECT_STATE.md not found: ${e}`);
            }
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('multiAgent.restartServer', () => {
        if (serverProcess) {
            serverProcess.kill();
            serverProcess = null;
        }
        startPythonServer(context);
        vscode.window.showInformationMessage('Multi-Agent Backend Server restarted.');
    }));
}
function deactivate() {
    if (serverProcess) {
        serverProcess.kill();
        serverProcess = null;
    }
}
function startPythonServer(context) {
    if (serverProcess) {
        return;
    }
    const workspaceFolders = vscode.workspace.workspaceFolders;
    const workspacePath = workspaceFolders && workspaceFolders.length > 0 ? workspaceFolders[0].uri.fsPath : '';
    const systemServerScript = 'C:\\Users\\prana\\ai-kimi-coding-system\\server.py';
    const args = [systemServerScript];
    if (workspacePath) {
        args.push(workspacePath);
    }
    try {
        serverProcess = child_process.spawn('python', args, {
            cwd: workspacePath || 'C:\\Users\\prana\\ai-kimi-coding-system',
            env: { ...process.env }
        });
        serverProcess.stdout?.on('data', (data) => {
            console.log(`[Multi-Agent Server] ${data}`);
        });
        serverProcess.stderr?.on('data', (data) => {
            console.error(`[Multi-Agent Server Error] ${data}`);
        });
        if (serverProcess) {
            serverProcess.on('exit', () => {
                serverProcess = null;
            });
            serverProcess.on('error', () => {
                serverProcess = null;
            });
        }
    }
    catch (e) {
        serverProcess = null;
        console.error(`Failed to auto-start python server: ${e}`);
    }
}
class MultiAgentChatViewProvider {
    constructor(_context) {
        this._context = _context;
    }
    resolveWebviewView(webviewView, context, _token) {
        this._view = webviewView;
        startPythonServer(this._context);
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._context.extensionUri]
        };
        webviewView.webview.onDidReceiveMessage(async (message) => {
            if (message && message.command === 'openFile' && message.filePath) {
                try {
                    let fileUri;
                    const raw = String(message.filePath);
                    if (raw.startsWith('file:///')) {
                        fileUri = vscode.Uri.parse(raw);
                    }
                    else {
                        const ws = vscode.workspace.workspaceFolders;
                        const rootPath = ws && ws.length > 0 ? ws[0].uri.fsPath : '';
                        fileUri = vscode.Uri.file(path.resolve(rootPath, raw));
                    }
                    const doc = await vscode.workspace.openTextDocument(fileUri);
                    await vscode.window.showTextDocument(doc);
                }
                catch (err) {
                    vscode.window.showErrorMessage(`Failed to open file '${message.filePath}': ${err}`);
                }
            }
        });
        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
    }
    _getHtmlForWebview(webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._context.extensionUri, 'media', 'main.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._context.extensionUri, 'media', 'main.css'));
        const workspaceFolders = vscode.workspace.workspaceFolders;
        const workspacePath = workspaceFolders && workspaceFolders.length > 0 ? workspaceFolders[0].uri.fsPath : '';
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="${styleUri}" rel="stylesheet">
    <title>Multi-Agent Dev System</title>
    <script>
        window.workspacePath = ${JSON.stringify(workspacePath)};
    </script>
</head>
<body>
    <div class="app-header">
        <div class="header-top">
            <div class="brand">
                <span class="status-dot disconnected" id="connection-dot" title="Server status: Connecting..."></span>
                <span class="title">Multi-Agent System</span>
            </div>
            <div class="header-badges">
                <label class="toggle-control" title="Ask permission before file modifications and running commands">
                    <input type="checkbox" id="require-perm-toggle" checked />
                    <span class="toggle-slider"></span>
                    <span class="toggle-label">Ask Permission</span>
                </label>
                <span class="badge model-badge" id="model-badge">qwen3-coder</span>
            </div>
        </div>
        <div class="header-workspace" id="workspace-badge" title="Active workspace path">
            <span class="folder-icon">📁</span> <span id="workspace-path-text">${workspacePath ? workspacePath : 'No Workspace'}</span>
        </div>
    </div>

    <div class="tabs">
        <button class="tab-btn active" data-tab="chat-tab">
            <span class="tab-icon">💬</span> Chat & Manager
        </button>
        <button class="tab-btn" data-tab="state-tab">
            <span class="tab-icon">📋</span> Project State
        </button>
        <button class="tab-btn" data-tab="agents-tab">
            <span class="tab-icon">👥</span> Team & Skills
        </button>
    </div>

    <div id="chat-tab" class="tab-content active">
        <div id="chat-history" class="chat-history"></div>
        <div class="input-container">
            <div class="input-area">
                <textarea id="prompt-input" rows="2" placeholder="Ask Agent 5 to build, refactor, or test..."></textarea>
                <div class="button-group">
                    <button id="send-btn" class="primary-btn">
                        <span>Send</span> <span class="send-icon">🚀</span>
                    </button>
                    <button id="clear-btn" class="icon-btn" title="Clear chat history for current project">🗑️ Clear</button>
                </div>
            </div>
        </div>
    </div>

    <div id="state-tab" class="tab-content">
        <div class="tab-header-actions">
            <button id="refresh-state-btn" class="secondary-btn">🔄 Refresh State</button>
            <button id="open-state-btn" class="secondary-btn">📄 Open File</button>
        </div>
        <div id="state-viewer" class="state-viewer">Loading PROJECT_STATE.md...</div>
    </div>

    <div id="agents-tab" class="tab-content">
        <div id="agents-list">Loading agent team & skills...</div>
    </div>

    <script src="${scriptUri}"></script>
</body>
</html>`;
    }
}
MultiAgentChatViewProvider.viewType = 'multiAgent.chatView';
//# sourceMappingURL=extension.js.map