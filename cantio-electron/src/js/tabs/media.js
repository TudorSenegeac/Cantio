Tabs = Tabs || {};
Tabs.media = {
  onActivate() {
    this.setupEventListeners();
  },

  setupEventListeners() {
    if (this._setup) return;
    this._setup = true;

    document.getElementById('media-file')?.addEventListener('click', () => this.openVideo());
    document.getElementById('media-camera')?.addEventListener('click', () => this.openCamera());
    document.getElementById('media-cloud')?.addEventListener('click', () => this.openCloud());
  },

  async openVideo() {
    const result = await window.api.dialog.openFile({
      title: 'Selectează fișier video',
      filters: [
        { name: 'Video', extensions: ['mp4', 'avi', 'mov', 'mkv', 'webm'] },
        { name: 'Imagine', extensions: ['png', 'jpg', 'jpeg', 'gif', 'bmp'] },
      ],
      properties: ['openFile'],
    });
    if (result.canceled || !result.filePaths.length) return;
    const filePath = result.filePaths[0];
    const ext = filePath.split('.').pop()?.toLowerCase();
    const videoExts = ['mp4', 'avi', 'mov', 'mkv', 'webm'];

    if (videoExts.includes(ext)) {
      await window.api.media.startVideo(filePath);
      Utils.toast('Video pornit', 'success');
    } else {
      // Image as background
      await window.api.display.logo({ path: filePath });
      Utils.toast('Imagine setată ca fundal', 'success');
    }
  },

  async openCamera() {
    try {
      const constraints = { video: { width: { ideal: 1280 }, height: { ideal: 720 } } };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      // Create a video element and pipe to display
      const video = document.createElement('video');
      video.srcObject = stream;
      video.play();
      // Use canvas to capture frames and send to display
      const canvas = document.createElement('canvas');
      canvas.width = 640;
      canvas.height = 360;
      const ctx = canvas.getContext('2d');
      const capture = () => {
        if (video.readyState >= 2) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.5);
          window.api.display.show({ screenIndex: 0, text: '', metadata: { imageData: dataUrl }, transition: 'instant' });
        }
        requestAnimationFrame(capture);
      };
      capture();
      Utils.toast('Cameră activată', 'success');
    } catch (e) {
      Utils.toast('Eroare cameră: ' + e.message, 'error');
    }
  },

  async openCloud() {
    Utils.toast('Media cloud — în dezvoltare', 'info');
  },
};
