
import { world, system } from "@minecraft/server";
import { ActionFormData } from "@minecraft/server-ui";

const MUSIC_TRACKS = ["custom.jukebox.grimm_hollow_knight_the_grimm_troupe__christopher_larkin_youtube", "custom.jukebox.mc_orsen__warning_speed_up_extended_mix__bass_boosted__rocky_tiktok_edit__olderbrotheradvice_youtube", "custom.jukebox.musica1"];
// SEU ID (Verifique se bate com o jukebox.json)
const BLOCK_ID = "meu_addon:custom_jukebox"; 

// 1. EVENTO DE CLIQUE (Tocar Música)
world.afterEvents.playerInteractWithBlock.subscribe((event) => {
    const { block, player } = event;

    if (block.typeId === BLOCK_ID) {
        
        const form = new ActionFormData()
            .title("Jukebox")
            .body("Selecione o disco:");

        for (const track of MUSIC_TRACKS) {
            const name = track.split(".").pop().replace(/_/g, " ");
            form.button("♫ " + name);
        }
        form.button("§c■ Parar Som");

        system.run(() => {
            form.show(player).then((response) => {
                if (response.canceled) return;
                
                const selection = response.selection;

                // Coordenadas formatadas
                const x = block.location.x.toFixed(2);
                const y = block.location.y.toFixed(2);
                const z = block.location.z.toFixed(2);

                // Para sons anteriores num raio de 64 blocos
                player.dimension.runCommandAsync(`stopsound @a[x=${x},y=${y},z=${z},r=64]`);

                if (selection === MUSIC_TRACKS.length) {
                    player.sendMessage("§cSom parado.");
                    return;
                }

                const track = MUSIC_TRACKS[selection];

                // --- AJUSTE DE VOLUME E DISTÂNCIA ---
                // Volume 4.0 no comando = Raio de aprox 64 blocos.
                // Se passar disso, o som corta abruptamente ou fica inaudível.
                const cmd = `playsound ${track} @a ${x} ${y} ${z} 4.0 1.0`;
                
                player.dimension.runCommandAsync(cmd);
                player.sendMessage(`§aTocando: ${track}`);

            }).catch(e => console.error(e));
        });
    }
});

// 2. EVENTO DE QUEBRA (Parar Música)
world.afterEvents.playerBreakBlock.subscribe((event) => {
    const { block, brokenBlockPermutation } = event;

    // Verifica se o bloco quebrado era a nossa Jukebox
    if (brokenBlockPermutation.type.id === BLOCK_ID) {
        
        const x = block.location.x.toFixed(2);
        const y = block.location.y.toFixed(2);
        const z = block.location.z.toFixed(2);

        // Manda parar qualquer som num raio pequeno (4 blocos) ao redor de onde o bloco estava
        // Usamos executeCommand para garantir que pare para todos
        block.dimension.runCommandAsync(`stopsound @a[x=${x},y=${y},z=${z},r=10]`);
        
        // Mensagem opcional (pode remover se quiser)
        // console.warn("Jukebox quebrada, som interrompido.");
    }
});
