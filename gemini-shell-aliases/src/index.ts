import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';

// MCP Server for Gemini Shell Aliases Extension
console.log("MCP Server started.");

const extensionPath = process.env.GEMINI_EXTENSION_PATH || process.cwd();
const geminiExtensionJsonPath = path.join(extensionPath, 'gemini-extension.json');

interface JsonRpcRequest {
    jsonrpc: string;
    id: number;
    method: string;
    params?: any;
}

interface JsonRpcResponse {
    jsonrpc: string;
    id: number;
    result?: any;
    error?: any;
}

interface ToolDefinition {
    name: string;
    description: string;
    parameters: {
        type: string;
        properties: {
            [key: string]: {
                type: string;
                description: string;
            };
        };
        required?: string[];
    };
}

function sendResponse(response: JsonRpcResponse) {
    process.stdout.write(JSON.stringify(response) + '\n');
}

function sendError(id: number, code: number, message: string, data?: any) {
    sendResponse({
        jsonrpc: "2.0",
        id: id,
        error: { code, message, data }
    });
}

try {
    const geminiExtensionConfig = JSON.parse(fs.readFileSync(geminiExtensionJsonPath, 'utf8'));
    const aliasFiles = geminiExtensionConfig.configuration?.aliasFiles || [];
    console.log("Configured alias files:", aliasFiles);

    const aliases: { [key: string]: string } = {};
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
        } catch (fileError: any) {
            if (fileError.code === 'ENOENT') {
                console.warn(`Alias file not found: ${absoluteFilePath}`);
            } else {
                console.error(`Error reading alias file ${absoluteFilePath}:`, fileError);
            }
        }
    }
    console.log("All parsed aliases:", aliases);

    // JSON-RPC communication
    process.stdin.on('data', (data) => {
        const messages = data.toString().split('\n');
        for (const message of messages) {
            if (message.trim() === '') continue;
            try {
                const request: JsonRpcRequest = JSON.parse(message);
                console.log("Received request:", request);

                if (request.method === 'initialize') {
                    sendResponse({ jsonrpc: "2.0", id: request.id, result: {} });
                } else if (request.method === 'mcp/tools') {
                    const tools: ToolDefinition[] = [];
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
                } else if (request.method === 'mcp/executeTool') {
                    const toolName = request.params.name;
                    const toolArgs = request.params.args?.args || ''; // 'args' is nested
                    const aliasCommand = aliases[toolName];

                    if (aliasCommand) {
                        const commandToExecute = `${aliasCommand} ${toolArgs}`.trim();
                        exec(commandToExecute, (error, stdout, stderr) => {
                            if (error) {
                                sendError(request.id, 1, `Error executing alias '${toolName}': ${error.message}`, { stdout, stderr });
                            } else {
                                sendResponse({ jsonrpc: "2.0", id: request.id, result: { stdout, stderr } });
                            }
                        });
                    } else {
                        sendError(request.id, 2, `Alias '${toolName}' not found.`);
                    }
                } else {
                    sendError(request.id, -32601, "Method not found");
                }
            } catch (parseError) {
                console.error("Error parsing JSON-RPC message:", parseError);
                // Cannot send error response if ID is unknown
            }
        }
    });

} catch (error: any) {
    console.error("Error reading or parsing gemini-extension.json:", error);
}