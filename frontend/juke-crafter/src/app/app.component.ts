import { Component } from '@angular/core';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatRippleModule } from '@angular/material/core';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

interface TrackMeta {
  filename: string;
  playlist: string;
  icon_filename?: string;
}

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule,
    MatRippleModule, MatSnackBarModule, MatTooltipModule]
})
export class AppComponent {
  constructor(private http: HttpClient, private snack: MatSnackBar) {
    if (typeof window !== 'undefined') {
      this.loadTracks();
      this.syncLangFromUrl();
      window.addEventListener('popstate', () => this.syncLangFromUrl());
      this.installGlobalDropGuard();
    }
  }

  /**
   * Stop the browser from "opening" a file when the user drops it
   * anywhere outside our explicit drop zones (the default behaviour
   * navigates the tab to the file, which loses everything in state).
   */
  private installGlobalDropGuard() {
    const prevent = (e: DragEvent) => {
      // Skip the guard if the drop target is one of our explicit zones.
      const target = e.target as HTMLElement | null;
      if (target && target.closest && target.closest('.upload-body, .chip-droppable')) return;
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('dragover', prevent, false);
    window.addEventListener('drop', prevent, false);
  }

  // ---------- Track drag (track row -> playlist chip) -------------
  onTrackDragStart(event: DragEvent, trackId: string) {
    this.draggedTrackId = trackId;
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'move';
      // Some browsers require some data to actually start the drag.
      event.dataTransfer.setData('text/plain', trackId);
    }
  }

  onTrackDragEnd() {
    this.draggedTrackId = null;
    this.dragOverPlaylist = null;
  }

  onChipDragOver(event: DragEvent, playlist: string) {
    if (!this.draggedTrackId) return;  // ignore non-track drags
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    this.dragOverPlaylist = playlist;
  }

  onChipDragLeave(event: DragEvent, playlist: string) {
    if (this.dragOverPlaylist === playlist) this.dragOverPlaylist = null;
  }

  onChipDrop(event: DragEvent, playlist: string) {
    event.preventDefault();
    event.stopPropagation();
    const trackId =
      this.draggedTrackId ||
      (event.dataTransfer ? event.dataTransfer.getData('text/plain') : '');
    this.draggedTrackId = null;
    this.dragOverPlaylist = null;
    if (!trackId) return;
    const t = this.tracks.find(x => x.id === trackId);
    if (t && t.playlist !== playlist) {
      t.playlist = playlist;
      this.saveTracks();
      this.toast(`${this.t('movedToPlaylist')} "${playlist}"`);
    }
  }

  /** Read the current URL and set currentLang. Default = 'en'. */
  private syncLangFromUrl() {
    const path = (window.location.pathname || '').toLowerCase();
    if (path.startsWith('/pt-br')) this.currentLang = 'pt';
    else if (path.startsWith('/en-us')) this.currentLang = 'en';
    // else: keep whatever default is set on the class
  }

  /** Push the matching /pt-br or /en-us segment into the URL without reload. */
  private pushLangToUrl(lang: 'pt' | 'en') {
    if (typeof window === 'undefined') return;
    const target = lang === 'pt' ? '/pt-br' : '/en-us';
    const current = window.location.pathname || '/';
    if (current === target) return;
    window.history.pushState(null, '', target + window.location.search + window.location.hash);
  }

  nomeAddon = 'Meu_Pacote_De_Musicas';
  arquivosSelecionados: File[] = [];
  playlists: string[] = ['Geral'];
  metadados: TrackMeta[] = [];

  /** One-time clean up of stored state that may contain case duplicates
   *  created before the case-insensitive dedup was added. */
  private dedupPlaylists() {
    const seen = new Set<string>();
    const cleaned: string[] = [];
    for (const p of this.playlists) {
      const k = p.toLowerCase();
      if (!seen.has(k)) { seen.add(k); cleaned.push(p); }
    }
    if (cleaned.length !== this.playlists.length) this.playlists = cleaned;
  }

  // tracks CRUD (local cache)
  tracks: Array<{
    id: string;
    type: 'file' | 'youtube';
    filename?: string;       // original filename (mp3 case)
    file?: File | null;
    url?: string;            // youtube url
    playlist: string;
    displayName: string;     // user-editable; defaults to base filename or '' for yt
  }> = [];

  /** Returns ".mp3" / ".ogg" / etc from a filename, or ".mp3" as a safe default. */
  private extOf(name?: string): string {
    if (!name) return '.mp3';
    const m = name.match(/\.[^./\\]+$/);
    return m ? m[0] : '.mp3';
  }
  /** Strips the extension off a filename. */
  private baseOf(name?: string): string {
    if (!name) return '';
    return name.replace(/\.[^./\\]+$/, '');
  }
  /** Strip filesystem-illegal characters. */
  private sanitizeName(s: string): string {
    return (s || '').replace(/[\\/:*?"<>|]/g, '_').trim();
  }

  isCarregando = false;
  youtubeLinksText = '';
  linkPlaylist = 'Geral';
  currentLang: 'pt' | 'en' = 'en';
  navOpen = false;
  isDragOver = false;
  lastError: string | null = null;
  /** Set while the user is dragging a track around (HTML5 D&D). */
  draggedTrackId: string | null = null;
  /** Name of the playlist chip currently being hovered with a track. */
  dragOverPlaylist: string | null = null;

  // ---------- Build progress modal state -------------
  buildLog: Array<{ ts: string; msg: string }> = [];
  buildPhase: string = 'idle';
  buildProgress: { pct: number | null; label: string | null } | null = null;
  showLog = false;
  /** Number of pixel segments inside the Minecraft-style progress bar. */
  readonly segmentCount = 32;
  segments: number[] = Array.from({ length: 32 }, (_, i) => i);
  /** Index of the tip currently shown to the user. */
  currentTipIndex = 0;
  private logPollTimer: any = null;
  private tipTimer: any = null;

  get filledSegmentCount(): number {
    const pct = this.buildProgress?.pct;
    if (pct == null) return -1;  // indeterminate -> CSS handles marching
    return Math.max(0, Math.min(this.segmentCount, Math.round((pct / 100) * this.segmentCount)));
  }

  get currentTip(): string {
    const list = (this.labels[this.currentLang] as any).tips || [];
    if (list.length === 0) return '';
    return list[this.currentTipIndex % list.length];
  }

  // Image URLs — drop your custom PNGs into src/assets/icons/ to override.
  // If the file is missing, the inline SVG fallback in the template is used.
  imageUrls = {
    logo:    'assets/icons/jukeboxColorida.png',
    disc:    'assets/icons/amontoadoDiscos.png',
    folder:  'assets/icons/folder.png',
    youtube: 'assets/icons/youtube.png'
  };

  // Toggle to true once you have placed the custom images in /assets/icons/
  useCustomImages = true;

  // Translations
  labels: any = {
    pt: {
      title: 'Criador de Addon de Jukebox Bedrock',
      navHome: 'Início',
      navMyAddons: 'Meus Addons',
      navCommunity: 'Comunidade',
      navSupport: 'Suporte',
      aboutTitle: 'Sobre e Primeiros Passos',
      howToUse: 'Como Usar',
      howToInstall: 'Como Instalar',
      installLine1: 'Basta baixar o arquivo .mcaddon gerado e dar duplo clique.',
      installLine2: 'O Minecraft Bedrock Edition vai importar automaticamente seu pacote de jukebox personalizado! É só clicar no arquivo.',
      recipeTitle: 'Receita',
      recipeLine: 'No criador 3x3: P = qualquer tábua, D = qualquer disco, J = jukebox, N = pepita de ferro.',
      createPlaylists: 'Criar Playlists',
      uploadMp3s: 'Enviar MP3s',
      browseFiles: 'Procurar Arquivos',
      pasteYoutube: 'Colar Links do YouTube',
      addPlaylist: 'Adicionar Playlist',
      addSong: 'Adicionar Música',
      generateAddon: 'GERAR MOD (.mcaddon)',
      generating: 'Gerando...',
      uploadNote: 'Formatos: .mp3 .ogg .wav .m4a .flac (até 50MB por arquivo)',
      dropHint: 'ou arraste arquivos de áudio aqui',
      noAudioInDrop: 'Nenhum arquivo de áudio reconhecido nos itens soltos.',
      someRejected: 'Alguns arquivos não-áudio foram ignorados.',
      playlistForLinks: 'Playlist para os links',
      playlists: 'Playlists',
      tracks: 'Faixas',
      dragHere: 'Arraste as faixas aqui',
      nameAddon: 'Nome do Addon',
      playlistName: 'Nome da Playlist',
      youtubeUrl: 'Cole a URL do vídeo do YouTube...',
      youtubeNote: '*Links do YouTube são processados automaticamente.*',
      uploadOrPaste: 'Envie MP3s ou cole links do YouTube',
      nameTracks: 'Nomeie suas faixas',
      clickGenerate: 'Clique em "Gerar Mod"',
      footer: '© Criador de Addon de Jukebox 2024',
      noTracksAlert: 'Adicione pelo menos uma faixa ou link.',
      generateError: 'Falha ao gerar o addon',
      generateSuccess: 'Addon gerado com sucesso!',
      backendDown: 'Backend offline — o servidor uvicorn não respondeu (http://localhost:8000). Verifique se ele está rodando.',
      errorTitle: 'Erro ao gerar o addon',
      errorDismiss: 'Fechar',
      trackNamePlaceholder: 'Nome da faixa',
      youtubeNamePlaceholder: 'Nome (vazio = título do vídeo)',
      originalFile: 'Arquivo original',
      movedToPlaylist: 'Faixa movida para',
      dragHereHint: 'Arraste uma faixa em cima de uma playlist para reatribuir.',
      reuploadNeeded: 'Reenvie estes MP3s (perdidos após recarregar a página)',
      reuploadBadge: 'Reenviar',
      buildModalTitle: 'Carregando...',
      buildPhaseStarting: 'Iniciando...',
      buildPhaseUploading: 'Salvando arquivos enviados...',
      buildPhaseDownloading: 'Baixando do YouTube...',
      buildPhaseBuilding: 'Convertendo para .ogg e empacotando...',
      buildPhaseDone: 'Concluído!',
      buildLogTitle: 'Log do servidor',
      showDetails: 'Mostrar detalhes',
      hideDetails: 'Esconder detalhes',
      tips: [
        'Você pode criar várias playlists clicando em "Adicionar Playlist".',
        'Arraste uma faixa em cima de uma playlist para mover entre elas.',
        'O Music Player aparece no inventário do Modo Criativo após instalar.',
        'MP3, OGG, WAV, M4A e FLAC são suportados — o backend converte tudo pra .ogg.',
        'Renomeie a faixa antes de gerar para que o nome apareça bonito no jogo.',
        'Cole o link do YouTube e o backend baixa o áudio automaticamente.',
        'É uma boa ideia organizar suas músicas por playlists temáticas.',
        'O .mcaddon gerado é só dar duplo-clique e o Minecraft instala sozinho.',
        'Faixas longas podem demorar mais pra converter — o ffmpeg está trabalhando!',
        'Os ícones das faixas podem ser personalizados colocando um .png com o mesmo nome do .mp3.'
      ]
    },
    en: {
      title: 'Bedrock Jukebox Addon Maker',
      navHome: 'Home',
      navMyAddons: 'My Addons',
      navCommunity: 'Community',
      navSupport: 'Support',
      aboutTitle: 'About & Getting Started',
      howToUse: 'How to Use',
      howToInstall: 'How to Install',
      installLine1: 'Simply download your generated .mcaddon file and double-click it.',
      installLine2: 'Minecraft Bedrock Edition will automatically import your custom jukebox pack! Just click the file.',
      recipeTitle: 'Recipe',
      recipeLine: 'In the 3×3 grid: P = any plank, D = any music disc, J = jukebox, N = iron nugget.',
      createPlaylists: 'Create Playlists',
      uploadMp3s: 'Upload MP3s',
      browseFiles: 'Browse Files',
      pasteYoutube: 'Paste YouTube Links',
      addPlaylist: 'Add Playlist',
      addSong: 'Add Song',
      generateAddon: 'GENERATE MOD (.mcaddon)',
      generating: 'Generating...',
      uploadNote: 'Formats: .mp3 .ogg .wav .m4a .flac (Max 50MB per file)',
      dropHint: 'or drag audio files here',
      noAudioInDrop: 'No audio files recognized in the dropped items.',
      someRejected: 'Some non-audio files were ignored.',
      playlistForLinks: 'Playlist for links',
      playlists: 'Playlists',
      tracks: 'Tracks',
      dragHere: 'Drag tracks here',
      nameAddon: 'Addon Name',
      playlistName: 'Playlist Name',
      youtubeUrl: 'Paste YouTube Video URL...',
      youtubeNote: '*YouTube links are automatically processed.*',
      uploadOrPaste: 'Upload MP3s or paste YouTube links',
      nameTracks: 'Name your tracks',
      clickGenerate: 'Click "Generate Mod"',
      footer: '© Jukebox Addon Maker 2024',
      noTracksAlert: 'Add at least one track or link.',
      generateError: 'Failed to generate the addon',
      generateSuccess: 'Addon generated successfully!',
      backendDown: 'Backend is offline — uvicorn did not respond (http://localhost:8000). Make sure it is running.',
      errorTitle: 'Failed to generate the addon',
      errorDismiss: 'Dismiss',
      trackNamePlaceholder: 'Track name',
      youtubeNamePlaceholder: 'Name (empty = use video title)',
      originalFile: 'Original file',
      movedToPlaylist: 'Track moved to',
      dragHereHint: 'Drag a track onto a playlist chip to reassign it.',
      reuploadNeeded: 'Please re-upload these MP3s (lost after page reload)',
      reuploadBadge: 'Re-upload',
      buildModalTitle: 'Loading...',
      buildPhaseStarting: 'Starting...',
      buildPhaseUploading: 'Saving uploaded files...',
      buildPhaseDownloading: 'Downloading from YouTube...',
      buildPhaseBuilding: 'Converting to .ogg and packaging...',
      buildPhaseDone: 'Done!',
      buildLogTitle: 'Server log',
      showDetails: 'Show details',
      hideDetails: 'Hide details',
      tips: [
        'You can create multiple playlists by clicking "Add Playlist".',
        'Drag a track onto a playlist chip to move it between playlists.',
        'The Music Player appears in the Creative Inventory after install.',
        'MP3, OGG, WAV, M4A and FLAC are supported — backend converts everything to .ogg.',
        'Rename a track before generating so it shows up nicely in-game.',
        'Paste a YouTube link and the backend downloads the audio automatically.',
        'Organising your songs into themed playlists is a good idea.',
        'The generated .mcaddon just needs a double-click and Minecraft installs it.',
        'Long tracks take longer to convert — ffmpeg is working hard!',
        'Custom track icons: drop a .png with the same name next to the .mp3.'
      ]
    }
  };

  

  onFileSelected(event: any) {
    const files: FileList = event.target.files;
    this.addFiles(files);
  }

  /** Shared adder used by both <input> change and drag-and-drop. */
  private addFiles(files: FileList | File[]) {
    const arr = Array.from(files as any) as File[];
    if (arr.length === 0) return;
    const looksAudio = (f: File) =>
      /\.(mp3|ogg|wav|m4a|flac|aac|opus|wma|mp4)$/i.test(f.name) ||
      (f.type && f.type.startsWith('audio/'));
    const accepted = arr.filter(looksAudio);
    const rejected = arr.length - accepted.length;
    if (accepted.length === 0) {
      this.toast(this.t('noAudioInDrop'));
      return;
    }
    for (const f of accepted) {
      const id = cryptoRandomId();
      this.tracks.push({
        id, type: 'file',
        filename: f.name, file: f,
        playlist: 'Geral',
        displayName: this.baseOf(f.name),
      });
    }
    this.saveTracks();
    if (rejected > 0) this.toast(this.t('someRejected'));
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    // Only clear when we actually leave the drop zone, not when entering a child.
    const related = event.relatedTarget as Node | null;
    const current = event.currentTarget as Node | null;
    if (!current || !related || !current.contains(related)) {
      this.isDragOver = false;
    }
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) this.addFiles(files);
  }

  addYoutubeLink() {
    const url = this.youtubeLinksText && this.youtubeLinksText.trim();
    if (!url) return;
    const id = cryptoRandomId();
    this.tracks.push({
      id, type: 'youtube', url,
      playlist: this.linkPlaylist,
      displayName: '',  // empty -> backend keeps the YouTube video title
    });
    this.youtubeLinksText = '';
    this.saveTracks();
  }

  removeTrack(id: string) {
    this.tracks = this.tracks.filter(t => t.id !== id);
    this.saveTracks();
  }

  setPlaylistForTrack(id: string, playlist: string) {
    const t = this.tracks.find(x => x.id === id);
    if (t) { t.playlist = playlist; this.saveTracks(); }
  }

  saveTracks() {
    try {
      if (typeof window !== 'undefined' && (window as any).localStorage) {
        localStorage.setItem('juke_tracks_v1', JSON.stringify(this.tracks.map(t => ({
          id: t.id, type: t.type, filename: t.filename, url: t.url,
          playlist: t.playlist, displayName: t.displayName,
        }))));
      }
    } catch (e) { console.warn('Failed to save tracks', e); }
  }

  loadTracks() {
    try {
      if (typeof window !== 'undefined' && (window as any).localStorage) {
        const raw = localStorage.getItem('juke_tracks_v1');
        if (raw) {
          const parsed = JSON.parse(raw);
          this.tracks = parsed.map((p: any) => ({
            id: p.id, type: p.type, filename: p.filename, file: null, url: p.url,
            playlist: p.playlist,
            displayName: p.displayName ?? (p.type === 'file' ? this.baseOf(p.filename) : ''),
          }));
        }
      }
    } catch (e) { console.warn('Failed to load tracks', e); }
  }

  addPlaylist(name?: string) {
    const raw = (name ?? prompt('Playlist name:') ?? '').trim();
    if (!raw) return;
    // Case-insensitive dedup. Two playlists that differ only in case slug
    // to the same folder on disk and confuse the builder ("Pamonha" vs
    // "pamonha" both -> user_music/pamonha/).
    const lower = raw.toLowerCase();
    if (this.playlists.some(p => p.toLowerCase() === lower)) return;
    this.playlists.push(raw);
  }

  removePlaylist(name: string) {
    if (name === 'Geral') return;
    this.playlists = this.playlists.filter(p => p !== name);
    // Reatribui tracks dessa playlist para Geral
    this.tracks.forEach(t => { if (t.playlist === name) t.playlist = 'Geral'; });
    this.saveTracks();
  }

  private toast(msg: string, action = 'OK', ms = 3500) {
    this.snack.open(msg, action, { duration: ms, panelClass: ['mc-snack'] });
  }

  gerarAddon() {
    if (this.tracks.length === 0) { this.toast(this.t('noTracksAlert')); return; }

    // Catch file tracks whose actual blob was lost (page refresh, ng serve
    // reload, etc.). LocalStorage can't keep <File> objects, so a "phantom"
    // file track shows up in the list with t.file=null and would silently
    // get dropped from the upload. Surface that to the user instead.
    const orphans = this.tracks.filter(t => t.type === 'file' && !t.file);
    if (orphans.length > 0) {
      const names = orphans.map(o => o.displayName || o.filename || '?').join(', ');
      this.lastError = `${this.t('reuploadNeeded')}: ${names}`;
      this.toast(this.lastError, 'OK', 9000);
      return;
    }

    this.isCarregando = true;
    this.lastError = null;
    this.buildLog = [];
    this.buildPhase = 'starting';
    this.buildProgress = null;
    this.showLog = false;
    this.currentTipIndex = Math.floor(Math.random() * 999);
    this.startLogPolling();
    this.startTipRotation();
    const formData = new FormData();
    formData.append('nome_addon', this.nomeAddon);

    const metadados: any[] = [];
    const youtubeItems: Array<{ url: string; name: string; playlist: string }> = [];

    for (const t of this.tracks) {
      if (t.type === 'file' && t.file) {
        // Rename the File to honour the user's displayName before uploading.
        // The builder names tracks from the saved filename, so renaming here
        // is enough — no backend changes needed for files.
        const base = this.sanitizeName(t.displayName) || this.baseOf(t.filename) || 'track';
        const finalName = base + this.extOf(t.filename);
        const renamed = new File([t.file], finalName, { type: t.file.type });
        formData.append('arquivos', renamed, finalName);
        metadados.push({ filename: finalName, playlist: t.playlist });
      } else if (t.type === 'youtube' && t.url) {
        youtubeItems.push({
          url: t.url,
          name: this.sanitizeName(t.displayName),
          playlist: t.playlist,
        });
      }
    }

    // Clean up any case duplicates that snuck in from older sessions
    // ("Pamonha" + "pamonha" both slug to the same folder on disk).
    this.dedupPlaylists();

    formData.append('metadados_json', JSON.stringify(metadados));
    // Send the full playlist list so the backend can pass it through to
    // builder.py — that way empty playlists (like "Geral" with no tracks)
    // still show up in the in-game playlist picker.
    formData.append('playlists_json', JSON.stringify(this.playlists));
    if (youtubeItems.length > 0) {
      formData.append('youtube_items_json', JSON.stringify(youtubeItems));
    }

    this.http.post('http://localhost:8000/api/build-addon', formData, { responseType: 'blob' }).subscribe({
      next: (blob: Blob) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${this.nomeAddon}.mcaddon`;
        link.click();
        window.URL.revokeObjectURL(url);
        // Do one final poll to grab the "DONE" line and freeze on "done" phase,
        // then close the modal after a short pause so the user sees the success.
        this.pollLogOnce().finally(() => {
          this.stopLogPolling();
          this.stopTipRotation();
          setTimeout(() => {
            this.isCarregando = false;
            this.toast(this.t('generateSuccess'));
          }, 800);
        });
      },
      error: async (err) => {
        console.error('Erro ao gerar o Addon:', err);
        this.stopLogPolling();
        this.stopTipRotation();
        const serverMsg = await this.extractErrorMessage(err);
        const full = serverMsg
          ? `${this.t('generateError')} — ${serverMsg}`
          : this.t('generateError');
        this.lastError = full;
        this.toast(full, 'OK', 9000);
        this.isCarregando = false;
      }
    });
  }

  /** Poll the backend log endpoint while a build is in flight. */
  private startLogPolling() {
    this.stopLogPolling();
    const tick = () => this.pollLogOnce();
    tick();  // immediate first call
    this.logPollTimer = setInterval(tick, 1000);
  }

  private stopLogPolling() {
    if (this.logPollTimer) {
      clearInterval(this.logPollTimer);
      this.logPollTimer = null;
    }
  }

  /** Rotate the Minecraft-style tip every 5 seconds while the modal is open. */
  private startTipRotation() {
    this.stopTipRotation();
    this.tipTimer = setInterval(() => this.currentTipIndex++, 5000);
  }

  private stopTipRotation() {
    if (this.tipTimer) {
      clearInterval(this.tipTimer);
      this.tipTimer = null;
    }
  }

  toggleLog() { this.showLog = !this.showLog; }

  private pollLogOnce(): Promise<void> {
    return new Promise<void>((resolve) => {
      this.http.get<any>('http://localhost:8000/api/build-log').subscribe({
        next: (res) => {
          this.buildLog = res?.lines || [];
          this.buildPhase = res?.phase || 'idle';
          this.buildProgress = res?.progress || null;
          resolve();
        },
        error: () => resolve(),  // network blips are non-fatal
      });
    });
  }

  dismissError() { this.lastError = null; }

  /** Maps the backend "phase" string to a user-facing translation key. */
  phaseLabel(): string {
    switch (this.buildPhase) {
      case 'starting':    return this.t('buildPhaseStarting');
      case 'uploading':   return this.t('buildPhaseUploading');
      case 'downloading': return this.t('buildPhaseDownloading');
      case 'building':    return this.t('buildPhaseBuilding');
      case 'done':        return this.t('buildPhaseDone');
      default:            return this.t('buildPhaseStarting');
    }
  }

  /** The backend returns errors as JSON, but the HttpClient receives them
   *  as Blob (because we asked for blob). Convert back to a human string. */
  private async extractErrorMessage(err: any): Promise<string> {
    // No backend at all (CORS / connection refused)
    if (err && err.status === 0) return this.t('backendDown');

    const body = err && err.error;
    try {
      if (body instanceof Blob) {
        const text = await body.text();
        try {
          const obj = JSON.parse(text);
          if (obj && typeof obj.error === 'string') return obj.error;
          if (obj && typeof obj.detail === 'string') return obj.detail;
        } catch { return text || ''; }
      } else if (typeof body === 'string') {
        try {
          const obj = JSON.parse(body);
          return obj?.error || obj?.detail || body;
        } catch { return body; }
      } else if (body && typeof body === 'object') {
        return body.error || body.detail || JSON.stringify(body);
      }
    } catch { /* fall through */ }
    return err?.message || '';
  }

  t(key: string) {
    return (this.labels[this.currentLang] && this.labels[this.currentLang][key]) || key;
  }

  toggleLanguage() {
    this.currentLang = this.currentLang === 'pt' ? 'en' : 'pt';
    this.pushLangToUrl(this.currentLang);
  }
}

function cryptoRandomId(len = 8) {
  return Math.random().toString(36).slice(2, 2 + len) + Date.now().toString(36).slice(-4);
}
