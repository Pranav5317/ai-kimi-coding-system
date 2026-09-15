import * as vscode from 'vscode';
import * as child_process from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

let serverProcess: child_process.ChildProcess | null = null;
let outputChannel: vscode.OutputChannel | null = null;

function getOutputChannel(): vscode.OutputChannel {
    if (!outputChannel) {
        outputChannel = vscode.window.createOutputChannel('Multi-Agent Server');
    }
    return outputChannel;
}

export function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('multiAgent');
    if (config.get<boolean>('autoStartServer', true)) {
        startPythonServer(context);
    }

    const provider = new MultiAgentChatViewProvider(context);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(MultiAgentChatViewProvider.viewType, provider)
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('multiAgent.startServer', () => {
            startPythonServer(context);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('multiAgent.openState', async () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (workspaceFolders && workspaceFolders.length > 0) {
                const statePath = vscode.Uri.file(path.join(workspaceFolders[0].uri.fsPath, 'PROJECT_STATE.md'));
                try {
                    const doc = await vscode.workspace.openTextDocument(statePath);
                    await vscode.window.showTextDocument(doc);
                } catch (e) {
                    vscode.window.showErrorMessage(`PROJECT_STATE.md not found: ${e}`);
                }
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('multiAgent.restartServer', () => {
            if (serverProcess) {
                serverProcess.kill();
                serverProcess = null;
            }
            startPythonServer(context);
            vscode.window.showInformationMessage('Multi-Agent Backend Server restarted.');
        })
    );
}

export function deactivate() {
    if (serverProcess) {
        serverProcess.kill();
        serverProcess = null;
    }
}

function resolveServerScript(context: vscode.ExtensionContext, workspacePath: string, customPath: string): string | null {
    if (customPath) {
        const resolvedCustom = path.isAbsolute(customPath) ? customPath : path.resolve(workspacePath, customPath);
        if (fs.existsSync(resolvedCustom)) {
            return resolvedCustom;
        }
    }

    if (workspacePath) {
        const wsScript = path.join(workspacePath, 'server.py');
        if (fs.existsSync(wsScript)) {
            return wsScript;
        }
    }

    const extScript = path.join(context.extensionPath, 'server.py');
    if (fs.existsSync(extScript)) {
        return extScript;
    }

    const parentScript = path.join(context.extensionPath, '..', 'server.py');
    if (fs.existsSync(parentScript)) {
        return parentScript;
    }

    const fallbackScript = 'C:\\Users\\prana\\ai-kimi-coding-system\\server.py';
    if (fs.existsSync(fallbackScript)) {
        return fallbackScript;
    }

    return null;
}

function resolvePythonBinary(workspacePath: string, customPython: string): string {
    if (customPython && customPython !== 'python') {
        return customPython;
    }

    if (workspacePath) {
        const winVenv = path.join(workspacePath, '.venv', 'Scripts', 'python.exe');
        if (fs.existsSync(winVenv)) return winVenv;

        const winVenv2 = path.join(workspacePath, 'venv', 'Scripts', 'python.exe');
        if (fs.existsSync(winVenv2)) return winVenv2;

        const unixVenv = path.join(workspacePath, '.venv', 'bin', 'python');
        if (fs.existsSync(unixVenv)) return unixVenv;

        const unixVenv2 = path.join(workspacePath, 'venv', 'bin', 'python');
        if (fs.existsSync(unixVenv2)) return unixVenv2;
    }

    return 'python';
}

function startPythonServer(context: vscode.ExtensionContext) {
    if (serverProcess) {
        return;
    }

    const config = vscode.workspace.getConfiguration('multiAgent');
    const customPython = config.get<string>('pythonPath', 'python');
    const customScript = config.get<string>('serverScriptPath', '');
    const serverPort = config.get<number>('serverPort', 8000);
    const serverHost = config.get<string>('serverHost', '127.0.0.1');

    const workspaceFolders = vscode.workspace.workspaceFolders;
    const workspacePath = workspaceFolders && workspaceFolders.length > 0 ? workspaceFolders[0].uri.fsPath : '';

    const serverScript = resolveServerScript(context, workspacePath, customScript);
    if (!serverScript) {
        vscode.window.showErrorMessage('Multi-Agent Dev System: Could not locate server.py. Please set multiAgent.serverScriptPath in VS Code Settings.');
        return;
    }

    const provider = config.get<string>('provider', 'ollama');
    const apiKey = config.get<string>('apiKey', '');
    const modelName = config.get<string>('modelName', 'qwen3-coder:latest');

    const pythonBin = resolvePythonBinary(workspacePath, customPython);
    const args = [serverScript];
    if (workspacePath) {
        args.push(workspacePath);
    }
    args.push('--host', serverHost, '--port', String(serverPort));

    const out = getOutputChannel();
    out.appendLine(`[Launching Server] ${pythonBin} ${args.join(' ')} (Provider: ${provider}, Model: ${modelName})`);

    try {
        const cwd = workspacePath || path.dirname(serverScript);
        serverProcess = child_process.spawn(pythonBin, args, {
            cwd,
            env: {
                ...process.env,
                LLM_PROVIDER: provider,
                OPENAI_API_KEY: apiKey,
                LLM_MODEL: modelName
            }
        });

        serverProcess.stdout?.on('data', (data) => {
            out.appendLine(`[Server STDOUT] ${data}`);
        });

        serverProcess.stderr?.on('data', (data) => {
            out.appendLine(`[Server STDERR] ${data}`);
        });

        if (serverProcess) {
            (serverProcess as any).on('exit', (code: number | null) => {
                out.appendLine(`[Server Exit] Process exited with code ${code}`);
                serverProcess = null;
            });
            (serverProcess as any).on('error', (err: Error) => {
                out.appendLine(`[Server Error] ${err.message}`);
                serverProcess = null;
            });
        }
    } catch (e) {
        serverProcess = null;
        out.appendLine(`Failed to auto-start python server: ${e}`);
        vscode.window.showErrorMessage(`Failed to start Multi-Agent Python server: ${e}`);
    }
}

class MultiAgentChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'multiAgent.chatView';
    private _view?: vscode.WebviewView;

    constructor(private readonly _context: vscode.ExtensionContext) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;
        const config = vscode.workspace.getConfiguration('multiAgent');
        if (config.get<boolean>('autoStartServer', true)) {
            startPythonServer(this._context);
        }

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._context.extensionUri]
        };

        (webviewView.webview as any).onDidReceiveMessage(async (message: any) => {
            if (message && message.command === 'openFile' && message.filePath) {
                try {
                    let fileUri: vscode.Uri;
                    const raw = String(message.filePath);
                    if (raw.startsWith('file:///')) {
                        fileUri = (vscode.Uri as any).parse(raw);
                    } else {
                        const ws = vscode.workspace.workspaceFolders;
                        const rootPath = ws && ws.length > 0 ? ws[0].uri.fsPath : '';
                        fileUri = vscode.Uri.file(path.resolve(rootPath, raw));
                    }
                    const doc = await vscode.workspace.openTextDocument(fileUri);
                    await vscode.window.showTextDocument(doc);
                } catch (err) {
                    vscode.window.showErrorMessage(`Failed to open file '${message.filePath}': ${err}`);
                }
            }
        });

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this._context.extensionUri, 'media', 'main.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this._context.extensionUri, 'media', 'main.css'));

        const config = vscode.workspace.getConfiguration('multiAgent');
        const serverPort = config.get<number>('serverPort', 8000);
        const serverHost = config.get<string>('serverHost', '127.0.0.1');
        const provider = config.get<string>('provider', 'ollama');
        const modelName = config.get<string>('modelName', 'qwen3-coder:latest');

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
        window.serverPort = ${JSON.stringify(serverPort)};
        window.serverHost = ${JSON.stringify(serverHost)};
        window.provider = ${JSON.stringify(provider)};
        window.modelName = ${JSON.stringify(modelName)};
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

