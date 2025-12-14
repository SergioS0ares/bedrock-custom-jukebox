# 🎵 Bedrock Custom Jukebox (AudioCraft)

Um addon para Minecraft Bedrock Edition que implementa um sistema avançado de áudio, permitindo aos jogadores "gravar" músicas em discos virgens e tocá-las em uma Jukebox personalizada.

> **Nota:** Este projeto utiliza a Script API (Beta) do Minecraft Bedrock.

## 🚀 Funcionalidades

- **Jukebox Customizada:** Um novo bloco com geometria 3D e interface própria.
- **Discos Virgens:** Itens craftáveis que podem receber dados.
- **Sistema de Gravação:** Escolha faixas de áudio pré-definidas no resource pack e grave-as no disco usando a UI do jogo.
- **Script API:** Lógica inteiramente feita em TypeScript/JavaScript para gerenciar o estado dos blocos e itens.

## 🛠️ Estrutura do Projeto

O projeto segue a estrutura padrão de desenvolvimento Bedrock:

- `/BP`: Behavior Pack (Lógica, Entidades, Scripts)
- `/RP`: Resource Pack (Texturas, Sons, Modelos, UI)
- `/scripts`: Código fonte TypeScript (se estiver compilando)

## 📦 Como Instalar

1. Baixe o arquivo `.mcaddon` na aba [Releases].
2. Execute o arquivo para importar no Minecraft.
3. Nas configurações do mundo, ative:
   - **Beta APIs** (Essencial para os scripts rodarem)
   - **Holiday Creator Features** (Para blocos customizados)

## 💻 Desenvolvimento

### Requisitos
- Visual Studio Code
- Extensão "Bedrock Definitions"
- Node.js (opcional, para compilação de TS)

### Clonando o repositório
```bash
git clone [[https://github.com/SEU-USUARIO/bedrock-custom-jukebox.git](https://github.com/SEU-USUARIO/bedrock-custom-jukebox.git](https://github.com/SergioS0ares/bedrock-custom-jukebox.git))
