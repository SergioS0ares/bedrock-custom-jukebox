FONTE MINECRAFTIA — INSTALAÇÃO
==============================

Minecraftia é a fonte fan-made mais usada para simular o chat e os menus
do Minecraft em sites. Ela não está no Google Fonts, então precisa ser
baixada e colocada nesta pasta.

PASSOS:
1. Baixe a fonte em: https://www.dafont.com/minecraftia.font
2. Extraia o ZIP.
3. Copie o arquivo "Minecraftia-Regular.ttf" para esta pasta:
   frontend/juke-crafter/src/assets/fonts/Minecraftia-Regular.ttf
   (se o arquivo vier com outro nome, renomeie para Minecraftia-Regular.ttf
    ou Minecraftia.ttf — o @font-face em styles.css aceita os dois nomes)
4. Reinicie o `ng serve`.

Enquanto o arquivo não estiver presente, o site usa "Pixelify Sans" como
fallback (que já é bem parecida com a do Minecraft).
