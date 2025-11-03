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
var _a;
Object.defineProperty(exports, "__esModule", { value: true });
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const child_process_1 = require("child_process");
// MCP Server for Gemini Shell Aliases Extension
console.log("MCP Server started.");
const extensionPath = process.env.GEMINI_EXTENSION_PATH || process.cwd();
const geminiExtensionJsonPath = path.join(extensionPath, 'gemini-extension.json');
function sendResponse(response) {
    process.stdout.write(JSON.stringify(response) + '\n');
}
function sendError(id, code, message, data) {
    sendResponse({
        jsonrpc: "2.0",
        id: id,
        error: { code, message, data }
    });
}
try {
    const geminiExtensionConfig = JSON.parse(fs.readFileSync(geminiExtensionJsonPath, 'utf8'));
    const aliasFiles = ((_a = geminiExtensionConfig.configuration) === null || _a === void 0 ? void 0 : _a.aliasFiles) || [];
    console.log("Configured alias files:", aliasFiles);
    const aliases = {};
    const aliasRegex = /^alias\s+([a-zA-Z0-9_]+)=['"](.*)['"]$/;
    for (const relativeFilePath of aliasFiles) {
        const absoluteFilePath = path.resolve(extensionPath, relativeFilePath);
        try {
            const fileContent = fs.readFileSync(absoluteFilePath, 'utf8');
            const lines = fileContent.split('\n');
            for (const line of lines) {
                const match = line.match(aliasRegex);
                if (match) {
                    const aliasName = match[1];
                    const aliasCommand = match[2];
                    aliases[aliasName] = aliasCommand;
                    console.log(`Parsed alias: ${aliasName} -> ${aliasCommand}`);
                }
            }
        }
        catch (fileError) {
            if (fileError.code === 'ENOENT') {
                console.warn(`Alias file not found: ${absoluteFilePath}`);
            }
            else {
                console.error(`Error reading alias file ${absoluteFilePath}:`, fileError);
            }
        }
    }
    console.log("All parsed aliases:", aliases);
    // JSON-RPC communication
    process.stdin.on('data', (data) => {
        var _a;
        const messages = data.toString().split('\n');
        for (const message of messages) {
            if (message.trim() === '')
                continue;
            try {
                const request = JSON.parse(message);
                console.log("Received request:", request);
                if (request.method === 'initialize') {
                    sendResponse({ jsonrpc: "2.0", id: request.id, result: {} });
                }
                else if (request.method === 'mcp/tools') {
                    const tools = [];
                    for (const aliasName in aliases) {
                        tools.push({
                            name: aliasName,
                            description: `Executes the shell alias '${aliasName}' which runs: ${aliases[aliasName]}`,
                            parameters: {
                                type: "object",
                                properties: {
                                    args: {
                                        type: "string",
                                        description: "Optional arguments to pass to the alias command."
                                    }
                                }
                            }
                        });
                    }
                    sendResponse({ jsonrpc: "2.0", id: request.id, result: tools });
                }
                else if (request.method === 'mcp/executeTool') {
                    const toolName = request.params.name;
                    const toolArgs = ((_a = request.params.args) === null || _a === void 0 ? void 0 : _a.args) || ''; // 'args' is nested
                    const aliasCommand = aliases[toolName];
                    if (aliasCommand) {
                        const commandToExecute = `${aliasCommand} ${toolArgs}`.trim();
                        (0, child_process_1.exec)(commandToExecute, (error, stdout, stderr) => {
                            if (error) {
                                sendError(request.id, 1, `Error executing alias '${toolName}': ${error.message}`, { stdout, stderr });
                            }
                            else {
                                sendResponse({ jsonrpc: "2.0", id: request.id, result: { stdout, stderr } });
                            }
                        });
                    }
                    else {
                        sendError(request.id, 2, `Alias '${toolName}' not found.`);
                    }
                }
                else {
                    sendError(request.id, -32601, "Method not found");
                }
            }
            catch (parseError) {
                console.error("Error parsing JSON-RPC message:", parseError);
                // Cannot send error response if ID is unknown
            }
        }
    });
}
catch (error) {
    console.error("Error reading or parsing gemini-extension.json:", error);
}
