import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, Download, History, Image as ImageIcon, Video, CheckCircle2, Clock, Trash2, 
  SortAsc, SortDesc, Loader2, Square, Calendar, CalendarDays, RefreshCw, Layers, 
  CheckSquare, FolderInput, FolderOpen, FolderSearch, AlertCircle, Sparkles, Zap, 
  Play, Pause, XCircle, RotateCcw, WifiOff, Wand2, Settings, Key, Film
} from 'lucide-react';

import { initializeApp } from "firebase/app";
import { getAuth, signInAnonymously, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, collection, addDoc, onSnapshot, deleteDoc, doc, serverTimestamp } from 'firebase/firestore';

// --- FIREBASE CONFIG ---
const firebaseConfig = {
  apiKey: "AIzaSyBypCNcrXr8ZP1uZ1OcdtORW4Y6PTwVxqU",
  authDomain: "reelsdownloader-319d3.firebaseapp.com",
  projectId: "reelsdownloader-319d3",
  storageBucket: "reelsdownloader-319d3.firebasestorage.app",
  messagingSenderId: "874238361346",
  appId: "1:874238361346:web:fa584e3db4905bd777cc1b",
  measurementId: "G-KKV138PEFM"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const appId = "reels-downloader";

// --- API BACKEND ---
const apiBackend = {
  analyzeUrl: async (targetUrl, cookie = '') => {
    try {
      const headers = {};
      if (cookie) headers['x-cookies'] = cookie;
      
      const response = await fetch(`/api/analyze?url=${encodeURIComponent(targetUrl)}`, {
        method: 'GET',
        headers: headers
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Lỗi server (${response.status})`);
      }
      return await response.json();
    } catch (error) {
      console.error("API Error:", error);
      throw error;
    }
  }
};

const mockPythonBackend = {
  analyzeUrl: async () => new Promise(r => setTimeout(() => r({ status: 'connected' }), 1000))
};

// Hàm tạo Mock Data
const generateSingleMockItem = (index, baseTime) => {
  const isVideo = index % 2 === 0; 
  const timeOffset = index * (Math.random() * 24 + 2) * 60 * 60 * 1000;
  const itemDate = new Date(baseTime.getTime() - timeOffset);
  const videoUrl = 'https://www.w3schools.com/html/mov_bbb.mp4'; 

  return {
    id: `media-${Date.now()}-${index}`,
    type: isVideo ? 'video' : 'image',
    thumbnail: null, 
    downloadUrl: isVideo ? videoUrl : `https://placehold.co/600x600/1a1a2e/FFF.png?text=Image_${index + 1}.jpg`,
    uploadedAt: itemDate.toISOString(),
    size: isVideo ? `${(Math.random() * 20 + 5).toFixed(1)} MB` : `${(Math.random() * 2 + 0.5).toFixed(1)} MB`,
    duration: isVideo ? `${Math.floor(Math.random() * 60 + 15)}s` : null,
    selected: true,
    rawDate: itemDate
  };
};

const TIME_RANGES = [
  { id: '1m', label: '1 tháng qua' },
  { id: '2m', label: '2 tháng qua' },
  { id: '3m', label: '3 tháng qua' },
  { id: 'all', label: 'Tất cả' },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('download'); 
  const [timeRange, setTimeRange] = useState('1m'); 
  const [fbCookie, setFbCookie] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [savePath, setSavePath] = useState('Downloads (Mặc định)');
  const [downloadOptions, setDownloadOptions] = useState({ video: true, image: true });
  const [folderError, setFolderError] = useState('');
  const [url, setUrl] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzedData, setAnalyzedData] = useState(null);
  const [sortOrder, setSortOrder] = useState('desc');
  const [limitCount, setLimitCount] = useState(0);
  
  const [downloadState, setDownloadState] = useState({
    isDownloading: false,
    isPaused: false,
    progress: 0,
    currentFileIndex: 0,
    totalFiles: 0,
    status: 'idle',
    error: null,
    currentAction: ''
  });
  
  const [mediaTab, setMediaTab] = useState('all'); 
  const downloadStateRef = useRef(downloadState); 
  const downloadIntervalRef = useRef(null);
  const analysisIntervalRef = useRef(null);
  const startTimeRef = useRef(null);
  const cutoffTimeRef = useRef(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  useEffect(() => { downloadStateRef.current = downloadState; }, [downloadState]);

  useEffect(() => {
    const initAuth = async () => {
      try { await signInAnonymously(auth); } catch (e) { console.error("Auth Error:", e); }
    };
    initAuth();
    return onAuthStateChanged(auth, setUser);
  }, []);

  useEffect(() => {
    if (!user) return;
    const q = collection(db, 'artifacts', appId, 'users', user.uid, 'download_history');
    return onSnapshot(q, (snap) => {
      const items = snap.docs.map(doc => ({ id: doc.id, ...doc.data(), timestamp: doc.data().timestamp?.toDate ? doc.data().timestamp.toDate() : new Date() }));
      items.sort((a, b) => b.timestamp - a.timestamp);
      setHistoryItems(items);
      setLoadingHistory(false);
    }, () => setLoadingHistory(false));
  }, [user]);

  const handleStartAnalysis = async () => {
    if (!url) return;
    setIsAnalyzing(true);
    setAnalyzedData([]);
    setLimitCount(0);

    try {
      const result = await apiBackend.analyzeUrl(url, fbCookie);
      
      const items = (result.results || []).map((item, index) => ({
        id: `media-${Date.now()}-${index}`,
        type: item.type || 'video',
        thumbnail: item.thumbnail, 
        downloadUrl: item.url, 
        uploadedAt: new Date().toISOString(),
        size: 'Unknown',
        title: item.title,
        selected: true
      }));

      if (items.length === 0) {
         console.log("API rỗng, chuyển sang Mock...");
         await mockPythonBackend.analyzeUrl();
         startMockAnalysis(); 
      } else {
         setAnalyzedData(items);
         setLimitCount(items.length);
         setIsAnalyzing(false);
      }
    } catch (error) {
      console.warn("API Error, fallback:", error);
      startMockAnalysis();
    }
  };

  const startMockAnalysis = () => {
    const now = new Date();
    startTimeRef.current = now;
    cutoffTimeRef.current = null;
    
    let itemsFound = 0;
    analysisIntervalRef.current = setInterval(() => {
      itemsFound++;
      const newItem = generateSingleMockItem(itemsFound, startTimeRef.current);
      setAnalyzedData(prev => {
        const newData = [...(prev || []), newItem];
        setLimitCount(newData.length);
        return newData;
      });
      if (itemsFound >= 20) { 
        clearInterval(analysisIntervalRef.current);
        setIsAnalyzing(false);
      }
    }, 300);
  };

  const toggleAnalysis = () => !isAnalyzing && handleStartAnalysis();
  const toggleSelection = (id) => setAnalyzedData(prev => prev.map(item => item.id === id ? { ...item, selected: !item.selected } : item));

  const downloadRealFile = async (fileUrl, fileName) => {
    try {
      const proxyUrl = `/api/download?url=${encodeURIComponent(fileUrl)}&filename=${encodeURIComponent(fileName)}`;
      const response = await fetch(proxyUrl);
      if (!response.ok) throw new Error('Proxy error');
      
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
      return true;
    } catch (error) {
      console.error("Download Error:", error);
      return false;
    }
  };

  const startDownload = async () => {
    if (!user || !filteredMedia.length) return;
    const itemsToDownload = filteredMedia.filter(item => item.selected && ((downloadOptions.video && item.type === 'video') || (downloadOptions.image && item.type === 'image')));
    if (itemsToDownload.length === 0) return;

    const newState = {
      isDownloading: true,
      isPaused: false,
      progress: 0,
      currentFileIndex: 0,
      totalFiles: itemsToDownload.length,
      status: 'downloading',
      error: null,
      currentAction: 'Đang kết nối server...'
    };
    
    setDownloadState(newState);
    downloadStateRef.current = newState;
    processDownloadQueue(itemsToDownload, 0);
  };

  const processDownloadQueue = async (items, startIndex) => {
    for (let i = startIndex; i < items.length; i++) {
      if (downloadStateRef.current.isPaused) {
        setDownloadState(prev => ({ ...prev, currentFileIndex: i, status: 'paused', currentAction: 'Đã tạm dừng' }));
        return; 
      }
      if (!downloadStateRef.current.isDownloading) return; 

      const item = items[i];
      setDownloadState(prev => ({
        ...prev,
        currentFileIndex: i,
        progress: 10,
        status: 'downloading',
        currentAction: `Đang tải ${item.title || 'file'}...`
      }));

      await new Promise(r => setTimeout(r, 500));
      setDownloadState(prev => ({ ...prev, progress: 50 }));

      const ext = item.type === 'video' ? 'mp4' : 'jpg';
      const fileName = `reels_${item.id}.${ext}`;
      await downloadRealFile(item.downloadUrl, fileName);

      setDownloadState(prev => ({ ...prev, progress: 100 }));
      await new Promise(r => setTimeout(r, 200)); 
    }

    finishDownload(items);
    setDownloadState(prev => ({ ...prev, progress: 100, currentFileIndex: items.length, status: 'completed', currentAction: 'Hoàn tất!' }));
  };

  const handleSelectFolder = async () => {
    setFolderError('');
    try {
      if (window.showDirectoryPicker) {
        const dir = await window.showDirectoryPicker({ startIn: 'downloads', mode: 'readwrite' });
        setSavePath(`Downloads/${dir.name}`);
      } else { setFolderError("Trình duyệt không hỗ trợ."); }
    } catch (err) { if (err.name !== 'AbortError') setFolderError("Lỗi bảo mật."); }
  };
  const pauseDownload = () => { setDownloadState(prev => ({ ...prev, isPaused: true })); downloadStateRef.current.isPaused = true; };
  const resumeDownload = () => {
    const nextIndex = downloadState.currentFileIndex;
    const items = filteredMedia.filter(item => item.selected);
    const newState = { ...downloadState, isPaused: false, status: 'downloading', isDownloading: true };
    setDownloadState(newState);
    downloadStateRef.current = newState;
    processDownloadQueue(items, nextIndex);
  };
  const cancelDownload = () => { setDownloadState({ isDownloading: false, isPaused: false, progress: 0, currentFileIndex: 0, totalFiles: 0, status: 'idle', error: null, currentAction: '' }); downloadStateRef.current.isDownloading = false; };
  const finishDownload = async (items) => {
    try {
      await addDoc(collection(db, 'artifacts', appId, 'users', user.uid, 'download_history'), {
        url: url, timestamp: serverTimestamp(), videoCount: items.length, totalFiles: items.length, savePath: savePath, status: 'success'
      });
      setTimeout(() => { setDownloadState(prev => ({ ...prev, isDownloading: false, status: 'idle' })); setActiveTab('history'); }, 2000);
    } catch (e) { console.error(e); }
  };
  const handleDeleteHistory = async (id) => { if (!user) return; try { await deleteDoc(doc(db, 'artifacts', appId, 'users', user.uid, 'download_history', id)); } catch (e) {} };

  const filteredMedia = useMemo(() => {
    if (!analyzedData) return [];
    let sorted = [...analyzedData];
    if (sortOrder === 'desc') sorted.reverse();
    return sorted.slice(0, limitCount || sorted.length);
  }, [analyzedData, sortOrder, limitCount]);

  const displayMedia = useMemo(() => {
    if (mediaTab === 'all') return filteredMedia;
    return filteredMedia.filter(item => item.type === mediaTab);
  }, [filteredMedia, mediaTab]);

  const stats = useMemo(() => {
    if (!filteredMedia) return { videos: 0, images: 0, selectedVideos: 0, selectedImages: 0 };
    return {
      videos: filteredMedia.filter(i => i.type === 'video').length,
      images: filteredMedia.filter(i => i.type === 'image').length,
      selectedVideos: filteredMedia.filter(i => i.type === 'video' && i.selected).length,
      selectedImages: filteredMedia.filter(i => i.type === 'image' && i.selected).length,
    };
  }, [filteredMedia]);

  const canDownload = useMemo(() => {
      if (downloadState.isDownloading || isAnalyzing) return false;
      const hasSelection = (downloadOptions.video && stats.selectedVideos > 0) || 
                           (downloadOptions.image && stats.selectedImages > 0);
      return hasSelection;
  }, [downloadState.isDownloading, isAnalyzing, downloadOptions, stats]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/40 to-slate-900 text-slate-100 font-sans selection:bg-pink-500/30 pb-20">
      <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-900/60 backdrop-blur-xl supports-[backdrop-filter]:bg-slate-900/30">
        <div className="max-w-4xl mx-auto px-4 h-20 flex items-center justify-between">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <div className="bg-gradient-to-tr from-indigo-500 to-pink-500 p-2 rounded-xl shadow-lg shadow-purple-500/20">
                <Sparkles size={20} className="text-white fill-white/20" />
              </div>
              <h1 className="font-bold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-purple-200">Reels Downloader</h1>
            </div>
            <p className="text-[10px] text-slate-400 mt-1 hidden sm:block font-medium">Phân tích, Tải xuống & Tối ưu nội dung</p>
          </div>
          <nav className="flex bg-white/5 p-1 rounded-xl border border-white/10 backdrop-blur-md">
            <button onClick={() => setActiveTab('download')} className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'download' ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}>Công cụ</button>
            <button onClick={() => setActiveTab('history')} className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'history' ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'}`}>Lịch sử</button>
          </nav>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {activeTab === 'download' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="bg-white/5 backdrop-blur-xl rounded-2xl p-6 shadow-2xl border border-white/10 space-y-6 relative overflow-hidden group">
              <div className="mb-4">
                 <button onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-2 text-xs text-purple-300 hover:text-purple-200 transition-colors">
                    <Settings size={14} /> Cấu hình nâng cao (Cookie Facebook)
                 </button>
                 {showAdvanced && (
                    <div className="mt-3 p-4 bg-black/40 rounded-xl border border-purple-500/20 animate-in slide-in-from-top-2">
                       <label className="block text-xs text-slate-400 mb-2 flex items-center gap-1">
                          <Key size={12} /> Cookie (c_user, xs...) - Dùng để tải video Private/Reels
                       </label>
                       <textarea value={fbCookie} onChange={(e) => setFbCookie(e.target.value)} placeholder="Dán chuỗi cookie vào đây..." className="w-full h-20 bg-black/20 border border-white/10 rounded-lg p-2 text-xs text-slate-300 font-mono focus:outline-none focus:border-purple-500 resize-none"/>
                       <p className="text-[10px] text-slate-500 mt-1">* Cách lấy: F12 &rarr; Network &rarr; Refresh &rarr; Request &rarr; Cookie.</p>
                    </div>
                 )}
              </div>

              <div className="relative z-10">
                <label className="text-sm font-medium text-purple-200 mb-3 flex items-center gap-2"><CalendarDays size={16} className="text-pink-400"/> Khoảng thời gian</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
                  {TIME_RANGES.map((range) => (
                    <label key={range.id} className={`relative flex items-center justify-center p-2 rounded-lg cursor-pointer transition-all ${timeRange === range.id ? 'bg-indigo-600 text-white shadow-lg font-semibold' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}>
                      <input type="radio" name="timeRange" value={range.id} checked={timeRange === range.id} onChange={() => setTimeRange(range.id)} disabled={isAnalyzing || downloadState.isDownloading} className="hidden"/>
                      <span className="text-xs sm:text-sm">{range.label}</span>
                    </label>
                  ))}
                </div>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><Search className="h-5 w-5 text-slate-500" /></div>
                    <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://instagram.com/reels/..." disabled={isAnalyzing || downloadState.isDownloading} className="block w-full pl-10 pr-3 py-3 bg-black/20 border border-white/10 rounded-xl focus:ring-2 focus:ring-purple-500 text-white placeholder-slate-600 transition-all disabled:opacity-60"/>
                  </div>
                  <button onClick={toggleAnalysis} disabled={!url && !isAnalyzing} className={`px-6 py-2 rounded-xl font-medium transition-all flex items-center gap-2 shadow-lg min-w-[140px] justify-center ${isAnalyzing ? 'bg-red-500/80 hover:bg-red-500 text-white' : 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white disabled:opacity-50'}`}>
                    {isAnalyzing ? <><Square size={18} fill="currentColor"/> Dừng</> : <><Zap size={18} fill="currentColor"/> Phân tích</>}
                  </button>
                </div>
              </div>
            </div>

            {(analyzedData && analyzedData.length > 0) && (
              <div className="space-y-6">
                <div className={`bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl transition-all duration-500 overflow-hidden flex flex-col ${isAnalyzing ? 'opacity-90' : 'opacity-100'}`}>
                  <div className="p-4 bg-black/20 min-h-[300px] max-h-[500px] overflow-y-auto custom-scrollbar">
                     <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
                        {displayMedia.map((item) => (
                          <div key={item.id} onClick={() => !isAnalyzing && !downloadState.isDownloading && toggleSelection(item.id)} className={`relative aspect-[3/4] rounded-xl overflow-hidden group border cursor-pointer transition-all ${item.selected ? 'border-purple-500 ring-2 ring-purple-500/30' : 'border-white/5 opacity-60'}`}>
                            {item.thumbnail ? (
                              <img src={item.thumbnail} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <div className={`w-full h-full flex flex-col items-center justify-center p-2 text-center bg-gradient-to-br ${item.type === 'video' ? 'from-purple-900 to-blue-900' : 'from-pink-900 to-rose-900'}`}>
                                {item.type === 'video' ? <Film size={32} className="text-white/50 mb-2"/> : <ImageIcon size={32} className="text-white/50 mb-2"/>}
                                <span className="text-xs text-white/70 font-medium">Content {item.id.split('-').pop()}</span>
                              </div>
                            )}
                            <div className="absolute top-1 right-1 bg-black/60 p-1.5 rounded-lg border border-white/10">{item.type === 'video' ? <Video size={10} className="text-white" /> : <ImageIcon size={10} className="text-white" />}</div>
                            {item.selected && <div className={`absolute inset-0 flex items-center justify-center transition-all bg-purple-900/20`}><div className="bg-purple-600 rounded-full p-1.5 shadow-lg"><CheckSquare size={16} className="text-white" /></div></div>}
                          </div>
                        ))}
                      </div>
                  </div>
                  
                  <div className="p-5 border-t border-white/5 bg-black/20 space-y-5">
                      <button onClick={startDownload} disabled={!canDownload} className="w-full sm:w-auto flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white py-3 px-8 rounded-xl font-bold shadow-lg shadow-purple-900/40 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group border border-white/10"><div className="flex items-center gap-2"><Download size={18} /><span>Tải xuống ngay</span></div></button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        {activeTab === 'history' && <div className="text-center text-slate-500">History UI</div>}
      </main>
    </div>
  );
}