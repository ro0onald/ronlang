const vscode = require('vscode');
const {execFile} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

function run(args) {
    return new Promise((resolve, reject) => {
        const executable = vscode.workspace.getConfiguration('ronlang').get('executable', 'ron');
        execFile(executable, args, {timeout: 10000, maxBuffer: 1048576, windowsHide: true}, (error, stdout) => {
            if (error && error.code !== 1) reject(error);
            else resolve({code: error ? 1 : 0, stdout});
        });
    });
}

function activate(context) {
    const diagnostics = vscode.languages.createDiagnosticCollection('ronlang');
    context.subscriptions.push(diagnostics);
    async function validate(document) {
        if (document.languageId !== 'ronlang' || !vscode.workspace.isTrusted || document.uri.scheme !== 'file') return;
        try {
            const version = document.version;
            const result = await run(['check', '--json', document.uri.fsPath]);
            if (version !== document.version) return;
            const entries = JSON.parse(result.stdout).map(error => new vscode.Diagnostic(
                new vscode.Range(Math.max(0, error.line-1), 0, Math.max(0, error.line-1), 1000),
                error.message, vscode.DiagnosticSeverity.Error));
            diagnostics.set(document.uri, entries);
        } catch (error) {
            diagnostics.set(document.uri, [new vscode.Diagnostic(new vscode.Range(0,0,0,1),
                'RonLang CLI unavailable. Install ron or configure ronlang.executable.', vscode.DiagnosticSeverity.Information)]);
        }
    }
    context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(validate));
    context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(validate));
    context.subscriptions.push(vscode.workspace.onDidCloseTextDocument(document => diagnostics.delete(document.uri)));
    vscode.workspace.textDocuments.forEach(validate);
    const words = ['make','show','func','return','when','otherwise','repeat','while','for','end','break','continue','use','require','try','catch','raise',
        'crear','mostrar','funcion','devolver','si','sino','repetir','mientras','para','fin','app','get','post','route','response','serve',
        'page','heading','paragraph','button','form','output','static','download','sessions','session_user','password_hash','password_verify',
        'login','logout','csrf','sql','postgres','migrate','read','write','json','parse_json','text','number','integer','length','range'];
    context.subscriptions.push(vscode.languages.registerCompletionItemProvider('ronlang', {
        provideCompletionItems(document) {
            const names = [...document.getText().matchAll(/(?:func|function|funcion)\s+([A-Za-z_]\w*)\s*\(/g)].map(m => m[1]);
            return [...new Set([...words, ...names])].map(word => new vscode.CompletionItem(word));
        }
    }));
    context.subscriptions.push(vscode.languages.registerDocumentFormattingEditProvider('ronlang', {
        async provideDocumentFormattingEdits(document) {
            if (!vscode.workspace.isTrusted) return [];
            const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ron-format-'));
            const file = path.join(directory, 'format.ron');
            try {
                fs.writeFileSync(file, document.getText(), 'utf8');
                const result = await run(['fmt', file]);
                if (result.code) return [];
                const all = new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length));
                return [vscode.TextEdit.replace(all, fs.readFileSync(file, 'utf8'))];
            } finally {
                fs.rmSync(directory, {recursive: true, force: true});
            }
        }
    }));
}
module.exports = {activate};
