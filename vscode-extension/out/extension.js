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
    }
    catch (e) {
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
        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
    }
    _getHtmlForWebview(webview) {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._context.extensionUri, 'media', 'main.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._context.extensionUri, 'media', 'main.css'));
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="${styleUri}" rel="stylesheet">
    <title>Multi-Agent Dev System</title>
</head>
<body>
    <div class="tabs">
        <button class="tab-btn active" data-tab="chat-tab">Chat & Manager</button>
        <button class="tab-btn" data-tab="state-tab">Project State</button>
        <button class="tab-btn" data-tab="agents-tab">Team Status</button>
    </div>

    <div id="chat-tab" class="tab-content active">
        <div id="chat-history" class="chat-history"></div>
        <div class="input-area">
            <textarea id="prompt-input" rows="2" placeholder="Ask Agent 5 to build or refactor..."></textarea>
            <button id="send-btn">Send</button>
        </div>
    </div>

    <div id="state-tab" class="tab-content">
        <div id="state-viewer" class="state-viewer">Loading PROJECT_STATE.md...</div>
    </div>

    <div id="agents-tab" class="tab-content">
        <div id="agents-list">Loading agents...</div>
    </div>

    <script src="${scriptUri}"></script>
</body>
</html>`;
    }
}
MultiAgentChatViewProvider.viewType = 'multiAgent.chatView';
//# sourceMappingURL=extension.js.map