import { ToolRegistry } from "../agentmesh/packages/toolkit/src/tools/ToolRegistry.js";
import { WorkspaceMCPClient } from "../agentmesh/packages/toolkit/src/integrations/WorkspaceMCPClient.js";

async function main() {
  const registry = new ToolRegistry();
  const client = new WorkspaceMCPClient(registry);

  // Connect with explicit minerva-mcp service (bypass discovery)
  (client as any).services = [
    {
      id: "minerva",
      name: "minerva",
      description: "Deep research system — MCP connection test",
      command: "/Users/xiamingxing/Workspace/minerva/.venv/bin/minerva-mcp",
    },
  ];

  console.log("Connecting to minerva-mcp...");
  const results = await client.connectAll();
  console.log(`  Status: ${results[0].status}`);
  if (results[0].error) console.log(`  Error: ${results[0].error}`);
  console.log(`  Tools discovered: ${results[0].tools.length}`);
  for (const t of results[0].tools) {
    console.log(`    - ${t}`);
  }

  // Register tools in registry
  const count = await client.registerAllTools();
  console.log(`\nTools registered in registry: ${count}`);
  console.log(`Client connected: ${client.isConnected()}`);

  // Print registered tool names
  if (count > 0) {
    const summary = client.getStatus();
    console.log(`\nConnection summary:`);
    console.log(`  Total services: ${summary.total}`);
    console.log(`  Connected: ${summary.connected}`);
    console.log(`  Errors: ${summary.errors}`);
  }

  client.disconnect();
  console.log("\nDisconnected. ✅");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
