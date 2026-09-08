declare module 'vscode' {
    export interface ExtensionContext {
        extensionUri: Uri;
        extensionPath: string;
        subscriptions: { push(disposable: any): void }[];
    }
    export interface Uri {
        fsPath: string;
    }
    export namespace Uri {
        function file(path: string): Uri;
        function joinPath(base: Uri, ...paths: string[]): Uri;
    }
    export namespace window {
        function registerWebviewViewProvider(providerId: string, provider: any): any;
        function showInformationMessage(message: string): void;
        function showErrorMessage(message: string): void;
        function showTextDocument(document: any): Promise<any>;
    }
    export namespace commands {
        function registerCommand(command: string, callback: (...args: any[]) => any): any;
    }
    export namespace workspace {
        function openTextDocument(uri: Uri): Promise<any>;
        var workspaceFolders: { uri: Uri }[] | undefined;
    }
    export interface WebviewView {
        webview: Webview;
    }
    export interface Webview {
        options: any;
        html: string;
        asWebviewUri(localResource: Uri): Uri;
    }
    export interface WebviewViewProvider {
        resolveWebviewView(webviewView: WebviewView, context: any, token: any): void;
    }
    export interface CancellationToken {}
    export interface WebviewViewResolveContext {}
}

declare module 'child_process' {
    export interface ChildProcess {
        kill(): void;
        stdout?: { on(event: string, listener: (data: any) => void): void };
        stderr?: { on(event: string, listener: (data: any) => void): void };
    }
    export function spawn(command: string, args?: string[], options?: any): ChildProcess;
}

declare module 'path' {
    export function join(...paths: string[]): string;
    export function resolve(...paths: string[]): string;
}

declare var process: {
    env: Record<string, string | undefined>;
};
declare var console: {
    log(...args: any[]): void;
    error(...args: any[]): void;
};

