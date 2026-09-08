import * as vscode from 'vscode';
import * as child_process from 'child_process';
import * as path from 'path';

let serverProcess: child_process.ChildProcess | null = null;

export function activate(context: vscode.ExtensionContext) {
    startPythonServer(context);

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
}

export function deactivate() {
    if (serverProcess) {
        serverProcess.kill();
        serverProcess = null;
    }
}

function startPythonServer(context: vscode.ExtensionContext) {
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
    } catch (e) {
        console.error(`Failed to auto-start python server: ${e}`);
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
        startPythonServer(this._context);

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._context.extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
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

