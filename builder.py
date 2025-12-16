import os
import json
import zipfile
import subprocess
import shutil

# --- CONFIGURAÇÕES ---
# Pega o diretório onde o script está rodando
BASE_DIR = os.path.abspath(os.getcwd())
NOME_ADDON = "JukeboxPro"

# Estrutura de pastas esperada
PASTA_SOURCE = os.path.join(BASE_DIR, "addon_source")
PASTA_MUSICA = os.path.join(BASE_DIR, "user_music")
FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")
PASTA_CACHE_AUDIO = os.path.join(BASE_DIR, "_audio_cache_")

# Template do arquivo JavaScript (main.js)
# Usamos player.dimension.runCommandAsync para evitar erros de contexto
JS_TEMPLATE = """
import { world, system } from "@minecraft/server";

// Lista de IDs de música gerada automaticamente pelo Python
const MUSIC_TRACKS = %MUSICAS_ARRAY%;

world.beforeEvents.playerInteractWithBlock.subscribe((event) => {
    const { player, block } = event;
    
    // Verifica se o bloco clicado é a nossa Jukebox
    if (block.typeId === "meu_addon:custom_jukebox") {
        const randomTrack = MUSIC_TRACKS[Math.floor(Math.random() * MUSIC_TRACKS.length)];
        
        // Toca o som para todos (@a) na posição do jogador
        // O comando playsound usa coordenadas relativas (~)
        player.runCommandAsync(`playsound ${randomTrack} @a ~ ~ ~ 10 1`);
        
        player.sendMessage(`§a[Jukebox] Tocando: ${randomTrack}`);
        
        // Cancela a interação para não abrir inventários (se houver)
        event.cancel = true; 
    }
});
"""

def main():
    print(f"--- INICIANDO BUILD JUKEBOX PRO ---")

    # 1. Limpeza de caches antigos
    if os.path.exists(PASTA_CACHE_AUDIO):
        shutil.rmtree(PASTA_CACHE_AUDIO)
    os.makedirs(PASTA_CACHE_AUDIO)

    # Preparar dicionários para o JSON
    musicas_ids = []
    sound_defs = {
        "format_version": "1.14.0",
        "sound_definitions": {}
    }

    contador = 0

    # 2. Verificar pastas
    if not os.path.exists(PASTA_MUSICA):
        os.makedirs(PASTA_MUSICA)
        print(f"ERRO: Pasta '{PASTA_MUSICA}' não existia. Ela foi criada. Coloque seus MP3 lá e rode novamente.")
        return

    arquivos_musica = [f for f in os.listdir(PASTA_MUSICA) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
    
    if not arquivos_musica:
        print(f"ERRO: Nenhum arquivo de música encontrado em '{PASTA_MUSICA}'.")
        return

    print(f"--- Encontradas {len(arquivos_musica)} músicas. Convertendo... ---")

    # 3. Conversão de Áudio com FFMPEG
    for arquivo in arquivos_musica:
        nome_base = os.path.splitext(arquivo)[0]
        # Limpa o nome (remove espaços e caracteres especiais para evitar bugs no Bedrock)
        nome_limpo = "".join(c for c in nome_base if c.isalnum() or c in ('_')).lower()
        
        caminho_entrada = os.path.join(PASTA_MUSICA, arquivo)
        nome_ogg = f"{nome_limpo}.ogg"
        caminho_saida = os.path.join(PASTA_CACHE_AUDIO, nome_ogg)

        print(f"Processando: {arquivo} -> {nome_ogg}")
        
        # COMANDOS ESSENCIAIS PARA O BEDROCK:
        # -ar 44100: Força 44.1kHz (Obrigatório)
        # -map_metadata -1: Remove capas de álbum que travam o som
        try:
            subprocess.run([
                FFMPEG_EXE, 
                '-y',                   # Sobrescrever sem perguntar
                '-i', caminho_entrada,  # Arquivo de entrada
                '-c:a', 'libvorbis',    # Codec OGG Vorbis
                '-ar', '44100',         # Frequência obrigatória
                '-ac', '2',             # Stereo (Use 1 para mono/3D)
                '-map_metadata', '-1',  # Limpar metadados
                caminho_saida
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print(f"ERRO CRÍTICO: Falha ao converter {arquivo}. Verifique se o ffmpeg.exe está na pasta.")
            return

        # Adicionar ao JSON de definições
        id_som = f"custom.music.{contador}"
        
        # IMPORTANTE: No JSON, o caminho NÃO tem extensão .ogg
        sound_defs["sound_definitions"][id_som] = {
            "category": "ui",  # "ui" ou "record"
            "sounds": [f"sounds/music/{nome_limpo}"]
        }
        musicas_ids.append(id_som)
        contador += 1

    # 4. Gerar o script main.js dinamicamente
    print("--- Gerando Script JS ---")
    script_content = JS_TEMPLATE.replace("%MUSICAS_ARRAY%", json.dumps(musicas_ids))
    
    # Salvar main.js na pasta do Behavior Pack
    path_scripts = os.path.join(PASTA_SOURCE, "BP", "scripts")
    if not os.path.exists(path_scripts):
        os.makedirs(path_scripts)
        
    with open(os.path.join(path_scripts, "main.js"), "w", encoding='utf-8') as f:
        f.write(script_content)

    # 5. Empacotar tudo no .mcaddon
    output_filename = os.path.join(BASE_DIR, f"{NOME_ADDON}.mcaddon")
    print(f"--- Criando arquivo final: {output_filename} ---")
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # A) Copiar toda a estrutura da pasta addon_source
        for root, dirs, files in os.walk(PASTA_SOURCE):
            for file in files:
                caminho_real = os.path.join(root, file)
                caminho_no_zip = os.path.relpath(caminho_real, PASTA_SOURCE)
                zipf.write(caminho_real, caminho_no_zip)

        # B) Adicionar as músicas convertidas na pasta correta (RP/sounds/music)
        for arquivo_ogg in os.listdir(PASTA_CACHE_AUDIO):
            caminho_real = os.path.join(PASTA_CACHE_AUDIO, arquivo_ogg)
            zipf.write(caminho_real, f"RP/sounds/music/{arquivo_ogg}")

        # C) CORREÇÃO CRÍTICA: Adicionar sound_definitions.json DENTRO de RP/sounds/
        # Se ficar na raiz do RP, o Minecraft ignora!
        zipf.writestr("RP/sounds/sound_definitions.json", json.dumps(sound_defs, indent=4))

    print("\n--- SUCESSO! ---")
    print(f"Arquivo gerado: {NOME_ADDON}.mcaddon")
    print("1. Delete a versão antiga no Minecraft (Armazenamento > Pacotes).")
    print("2. Instale este novo arquivo.")
    print("3. Teste com o bloco ou use: /playsound custom.music.0 @s")

if __name__ == "__main__":
    main()