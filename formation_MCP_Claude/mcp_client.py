import sys
import asyncio
from typing import Optional, Any
from contextlib import AsyncExitStack
import json

from pydantic import AnyUrl
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[dict] = None,
    ):
        # Commande pour lancer le serveur MCP (ex: "uv", args=["run", "mcp_server.py"])
        self._command = command
        self._args = args
        self._env = env
        self._session: Optional[ClientSession] = None
        # AsyncExitStack gere proprement l'ouverture et la fermeture des flux asynchrones
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def connect(self):
        """Lance le serveur MCP comme sous-processus et initialise la session de communication."""
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        # Ouvre la connexion bidirectionnelle via stdio (stdin/stdout)
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        _stdio, _write = stdio_transport
        
        # Cree la session cliente MCP au-dessus du transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_stdio, _write)
        )
        # Negociation initiale du protocole MCP (echange de capacites et versions)
        await self._session.initialize()

    def session(self) -> ClientSession:
        """Retourne la session active ou leve une exception si elle n'est pas connectee."""
        if self._session is None:
            raise ConnectionError(
                "Client session not initialized or cache not populated. Call connect_to_server first."
            )
        return self._session

    # --------------------------------------------------------------------------
    # GESTION DES OUTILS (TOOLS)
    # --------------------------------------------------------------------------
    async def list_tools(self) -> list[types.Tool]:
        """Interroge le serveur pour recuperer la liste de tous les outils disponibles.
        Cette liste est ensuite passee a Claude dans l'appel API pour qu'il sache quels outils existent."""
        result = await self.session().list_tools()
        return result.tools

    async def call_tool(
        self, tool_name: str, tool_input: dict
    ) -> types.CallToolResult | None:
        """Appelle un outil sur le serveur MCP lorsque Claude le demande (function calling).
        Transmet le nom de l'outil et les arguments fournis par le modele."""
        return await self.session().call_tool(tool_name, tool_input)

    # --------------------------------------------------------------------------
    # GESTION DES PROMPTS
    # --------------------------------------------------------------------------
    async def list_prompts(self) -> list[types.Prompt]:
        """Recupere la liste des prompts predefinis sur le serveur (utilise pour l'autocompletion Tab)."""
        result = await self.session().list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name, args: dict[str, str]):
        """Recupere les messages generes par un prompt specifique avec ses arguments 
        (ex: prompt_name='format', args={'doc_id': 'deposition.md'})."""
        result = await self.session().get_prompt(prompt_name, args)
        return result.messages

    # --------------------------------------------------------------------------
    # GESTION DES RESSOURCES
    # --------------------------------------------------------------------------
    async def read_resource(self, uri: str) -> Any:
        """Resout une URI (ex: 'docs://documents/deposition.md') et extrait son contenu.
        Declenche quand l'utilisateur mentionne '@deposition.md' dans son invite."""
        result = await self.session().read_resource(AnyUrl(uri))
        resource = result.contents[0]

        # Si la ressource est du texte, verifie si c'est du JSON ou du texte brut
        if isinstance(resource, types.TextResourceContents):
            if resource.mimeType == "application/json":
                return json.loads(resource.text)

            return resource.text

    # --------------------------------------------------------------------------
    # GESTION DU CYCLE DE VIE
    # --------------------------------------------------------------------------
    async def cleanup(self):
        """Ferme proprement la session et le processus sous-jacent."""
        await self._exit_stack.aclose()
        self._session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


# Point d'entree de test unitaire rapide du client
async def main():
    async with MCPClient(
        command="uv",
        args=["run", "mcp_server.py"],
    ) as client:
        result = await client.list_tools()
        print(result)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())