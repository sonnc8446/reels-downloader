// ... (Giữ nguyên các import)
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, Download, History, Image as ImageIcon, Video, CheckCircle2, Clock, Trash2, 
  SortAsc, SortDesc, Loader2, Square, Calendar, CalendarDays, RefreshCw, Layers, 
  CheckSquare, FolderInput, FolderOpen, FolderSearch, AlertCircle, Sparkles, Zap, 
  Play, Pause, XCircle, RotateCcw, WifiOff, Wand2
} from 'lucide-react';
// ... (Giữ nguyên các import firebase)
import { initializeApp } from "firebase/app";
import { getAuth, signInAnonymously, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, collection, addDoc, onSnapshot, deleteDoc, doc, serverTimestamp } from 'firebase/firestore';

// ... (Giữ nguyên Firebase Config)
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

// ... (Giữ nguyên apiBackend, mockPythonBackend, generateSingleMockItem, TIME_RANGES)
const apiBackend = {
  analyzeUrl: async (targetUrl) => {
    try {
      const response = await fetch(`/api/analyze?url=${encodeURIComponent(targetUrl)}`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Lỗi kết nối server (500)');
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

const generateSingleMockItem = (index, baseTime) => {
  const isVideo = index % 2 === 0; 
  const timeOffset = index * (Math.random() * 24 + 2) * 60 * 60 * 1000;
  const itemDate = new Date(baseTime.getTime() - timeOffset);

  return {
    id: `media-${Date.now()}-${index}`,
    type: isVideo ? 'video' : 'image',
    thumbnail: isVideo 
      ? 'https://placehold.co/600x800/2a1b3d/FFF.png?text=Video+Content' 
      : 'https://placehold.co/600x600/1a1a2e/FFF.png?text=Image+Content',
    downloadUrl: isVideo
      ? 'https://www.w3schools.com/html/mov_bbb.mp4' 
      : 'https://placehold.co/600x600/1a1a2e/FFF.png?text=Image+Download.jpg',
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
  { id: '6m', label: '6 tháng qua' },
  { id: 'all', label: 'Tất cả' },
  { id: 'custom', label: 'Tùy chọn' },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('download'); 
  const [timeRange, setTimeRange] = useState('1m'); 
  const [customDates, setCustomDates] = useState({ 
    from: new Date(new Date().setMonth(new Date().getMonth() - 1)).toISOString().split('T')[0], 
    to: new Date().toISOString().split('T')[0] 
  });
  
  // CẬP NHẬT: Hiển thị đúng logic của trình duyệt
  const [savePath, setSavePath] = useState('Downloads (Mặc định trình duyệt)');
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

  // ... (Giữ nguyên các useEffect)
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

  // ... (Giữ nguyên các hàm handler phân tích & download)
  const handleStartAnalysis = async () => {
    if (!url) return;
    setIsAnalyzing(true);
    setAnalyzedData([]);
    setLimitCount(0);

    try {
      const result = await apiBackend.analyzeUrl(url);
      
      const items = (result.results || []).map((item, index) => ({
        id: `media-${Date.now()}-${index}`,
        type: item.type || 'video',
        thumbnail: item.thumbnail,
        downloadUrl: item.url, 
        uploadedAt: new Date().toISOString(),
        size: 'Unknown',
        selected: true
      }));

      if (items.length === 0) {
         console.log("API rỗng, chuyển sang Mock Data Generator...");
         await mockPythonBackend.analyzeUrl();
         startMockAnalysis(); 
      } else {
         setAnalyzedData(items);
         setLimitCount(items.length);
         setIsAnalyzing(false);
      }
    } catch (error) {
      console.warn("API Error, switching to mock:", error);
      startMockAnalysis(); 
    }
  };

  const startMockAnalysis = () => {
    const now = new Date();
    let startPoint = now;
    let endPoint = null;

    if (timeRange === 'custom') {
       if (customDates.to) startPoint = new Date(customDates.to + 'T23:59:59');
       if (customDates.from) endPoint = new Date(customDates.from);
    } else if (timeRange !== 'all') {
       endPoint = new Date();
       const months = parseInt(timeRange.replace('m', ''));
       endPoint.setMonth(now.getMonth() - months);
    }

    startTimeRef.current = startPoint;
    cutoffTimeRef.current = endPoint;
    
    let itemsFound = 0;
    analysisIntervalRef.current = setInterval(() => {
      itemsFound++;
      const newItem = generateSingleMockItem(itemsFound, startTimeRef.current);
      
      if (cutoffTimeRef.current && newItem.rawDate < cutoffTimeRef.current) {
        clearInterval(analysisIntervalRef.current);
        setIsAnalyzing(false);
        return;
      }

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
        currentAction: `Đang tải ${item.type}: file ${i+1}/${items.length}...`
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

  const pauseDownload = () => {
    setDownloadState(prev => ({ ...prev, isPaused: true }));
    downloadStateRef.current.isPaused = true;
  };
  const resumeDownload = () => {
    const nextIndex = downloadState.currentFileIndex;
    const items = filteredMedia.filter(item => item.selected);
    const newState = { ...downloadState, isPaused: false, status: 'downloading', isDownloading: true };
    setDownloadState(newState);
    downloadStateRef.current = newState;
    processDownloadQueue(items, nextIndex);
  };
  const cancelDownload = () => {
    setDownloadState({ isDownloading: false, isPaused: false, progress: 0, currentFileIndex: 0, totalFiles: 0, status: 'idle', error: null, currentAction: '' });
    downloadStateRef.current.isDownloading = false;
  };
  const finishDownload = async (items) => {
    try {
      await addDoc(collection(db, 'artifacts', appId, 'users', user.uid, 'download_history'), {
        url: url, timestamp: serverTimestamp(),
        videoCount: items.length, totalFiles: items.length, savePath: savePath, status: 'success'
      });
      setTimeout(() => {
         setDownloadState(prev => ({ ...prev, isDownloading: false, status: 'idle' }));
         setActiveTab('history');
      }, 2000);
    } catch (e) { console.error(e); }
  };
  const handleDeleteHistory = async (id) => {
    if (!user) return;
    try { await deleteDoc(doc(db, 'artifacts', appId, 'users', user.uid, 'download_history', id)); } catch (e) {}
  };

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

  // CẬP NHẬT GIAO DIỆN CHỌN THƯ MỤC
  // Chỉ hiển thị thông báo, không gọi API showDirectoryPicker vì hạn chế bảo mật
  const handleSelectFolder = () => {
    alert("Do chính sách bảo mật của trình duyệt, file sẽ được tự động lưu vào thư mục 'Downloads' mặc định trên máy tính của bạn.");
    setSavePath('Downloads (Mặc định)');
    setFolderError('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900/40 to-slate-900 text-slate-100 font-sans selection:bg-pink-500/30 pb-20">
      <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-900/60 backdrop-blur-xl supports-[backdrop-filter]:bg-slate-900/30">
        <div className="max-w-4xl mx-auto px-4 h-20 flex items-center justify-between">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <div className="bg-gradient-to-tr from-indigo-500 to-pink-500 p-2 rounded-xl shadow-lg shadow-purple-500/20">
                <Sparkles size={20} className="text-white fill-white/20" />
              </div>
              <h1 className="font-bold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-purple-200">
                Reels Downloader
              </h1>
            </div>
            <p className="text-[10px] text-slate-400 mt-1 hidden sm:block font-medium">
              Phân tích, Tải xuống & Tối ưu nội dung
            </p>
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
              <div className="relative z-10">
                <label className="text-sm font-medium text-purple-200 mb-3 flex items-center gap-2"><CalendarDays size={16} className="text-pink-400"/> Khoảng thời gian</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                  {TIME_RANGES.map((range) => (
                    <label key={range.id} className={`relative flex items-center justify-center p-2 rounded-lg cursor-pointer transition-all ${timeRange === range.id ? 'bg-indigo-600 text-white shadow-lg font-semibold' : 'bg-white/5 text-slate-400 hover:bg-white/10'}`}>
                      <input type="radio" name="timeRange" value={range.id} checked={timeRange === range.id} onChange={() => setTimeRange(range.id)} disabled={isAnalyzing || downloadState.isDownloading} className="hidden"/>
                      <span className="text-xs sm:text-sm">{range.label}</span>
                    </label>
                  ))}
                </div>
                {timeRange === 'custom' && (
                  <div className="mt-4 p-4 bg-black/20 rounded-xl border border-white/5 animate-in slide-in-from-top-2 flex gap-4">
                    <div className="flex-1"><label className="text-xs text-slate-400 mb-1">Từ ngày</label><input type="date" value={customDates.from} onChange={(e) => setCustomDates(p => ({...p, from: e.target.value}))} className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-sm text-white focus:outline-none focus:border-purple-500"/></div>
                    <div className="flex-1"><label className="text-xs text-slate-400 mb-1">Đến ngày</label><input type="date" value={customDates.to} onChange={(e) => setCustomDates(p => ({...p, to: e.target.value}))} className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-sm text-white focus:outline-none focus:border-purple-500"/></div>
                  </div>
                )}
              </div>
              <div className="relative z-10">
                <label className="block text-sm font-medium text-purple-200 mb-2">URL Reels / Collection</label>
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
                  <div className="flex border-b border-white/5 bg-black/10">
                    {[{ id: 'all', label: 'Tất cả', count: filteredMedia.length, icon: Layers }, { id: 'video', label: 'Videos', count: stats.videos, icon: Video }, { id: 'image', label: 'Images', count: stats.images, icon: ImageIcon }].map(tab => (
                      <button key={tab.id} onClick={() => setMediaTab(tab.id)} className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium border-b-2 transition-all ${mediaTab === tab.id ? 'border-purple-500 text-purple-300 bg-purple-500/5' : 'border-transparent text-slate-400'}`}>
                        <tab.icon size={16} /> {tab.label} <span className="bg-white/10 text-[10px] px-1.5 py-0.5 rounded-full">{tab.count}</span>
                      </button>
                    ))}
                  </div>
                  
                  <div className="p-4 border-b border-white/5 flex justify-between items-center bg-black/10">
                     <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">Hiển thị: {limitCount}</span>
                        <input type="range" min="1" max={analyzedData.length} value={limitCount} onChange={(e) => setLimitCount(Number(e.target.value))} className="w-24 h-1 bg-white/20 rounded-lg accent-purple-500"/>
                     </div>
                     <div className="flex bg-black/20 rounded-lg p-1">
                        <button onClick={() => setSortOrder('desc')} className={`p-1.5 rounded ${sortOrder === 'desc' ? 'bg-white/10 text-white' : 'text-slate-500'}`}><SortDesc size={16}/></button>
                        <button onClick={() => setSortOrder('asc')} className={`p-1.5 rounded ${sortOrder === 'asc' ? 'bg-white/10 text-white' : 'text-slate-500'}`}><SortAsc size={16}/></button>
                     </div>
                  </div>

                  <div className="p-4 bg-black/20 min-h-[300px] max-h-[500px] overflow-y-auto custom-scrollbar">
                     <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
                        {displayMedia.map((item) => (
                          <div key={item.id} onClick={() => !isAnalyzing && !downloadState.isDownloading && toggleSelection(item.id)} className={`relative aspect-[3/4] rounded-xl overflow-hidden group border cursor-pointer transition-all ${item.selected ? 'border-purple-500 ring-2 ring-purple-500/30' : 'border-white/5 opacity-60'}`}>
                            <img src={item.thumbnail} alt="" className="w-full h-full object-cover" />
                            <div className="absolute top-1 right-1 bg-black/60 p-1.5 rounded-lg border border-white/10">{item.type === 'video' ? <Video size={10} className="text-white" /> : <ImageIcon size={10} className="text-white" />}</div>
                            {item.selected && <div className={`absolute inset-0 flex items-center justify-center transition-all bg-purple-900/20`}><div className="bg-purple-600 rounded-full p-1.5 shadow-lg"><CheckSquare size={16} className="text-white" /></div></div>}
                          </div>
                        ))}
                      </div>
                  </div>
                  <div className="p-5 border-t border-white/5 bg-black/20 space-y-5">
                     {downloadState.status !== 'idle' ? (
                       <div className="bg-white/5 border border-purple-500/30 rounded-xl p-5 animate-in slide-in-from-bottom-4 shadow-2xl relative overflow-hidden">
                          {downloadState.status === 'downloading' && <div className="absolute inset-0 bg-purple-500/5 animate-pulse pointer-events-none"></div>}
                          <div className="flex justify-between items-start mb-3 relative z-10">
                             <div>
                                <h3 className="text-white font-bold flex items-center gap-2">
                                   {downloadState.status === 'downloading' && <Loader2 className="animate-spin text-purple-400" size={18}/>}
                                   {downloadState.status === 'paused' && <Pause className="text-yellow-400" size={18}/>}
                                   {downloadState.status === 'completed' && <CheckCircle2 className="text-green-400" size={18}/>}
                                   {downloadState.status === 'error' && <WifiOff className="text-red-400" size={18}/>}
                                   <span className="tracking-tight">{downloadState.currentAction}</span>
                                </h3>
                             </div>
                             <div className="text-right"><span className="text-2xl font-bold text-white">{downloadState.currentFileIndex}</span><span className="text-sm text-slate-500">/{downloadState.totalFiles}</span></div>
                          </div>
                          <div className="h-2.5 bg-black/40 rounded-full overflow-hidden mb-4 relative z-10 border border-white/5">
                             <div className={`h-full transition-all duration-300 relative ${downloadState.status === 'paused' ? 'bg-yellow-500' : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500'}`} style={{ width: `${downloadState.progress}%` }}></div>
                          </div>
                          <div className="flex gap-3 justify-end relative z-10">
                             {downloadState.status === 'downloading' && <button onClick={pauseDownload} className="px-4 py-2 bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-200 rounded-lg text-xs font-bold border border-yellow-500/20 flex items-center gap-1.5 transition-all"><Pause size={14} fill="currentColor"/> Tạm dừng</button>}
                             {(downloadState.status === 'paused') && <button onClick={resumeDownload} className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-200 rounded-lg text-xs font-bold border border-green-500/20 flex items-center gap-1.5 transition-all"><Play size={14} fill="currentColor"/> Tiếp tục</button>}
                             <button onClick={cancelDownload} className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-300 rounded-lg text-xs font-bold border border-red-500/20 flex items-center gap-1.5 transition-all"><XCircle size={14}/> Hủy bỏ</button>
                          </div>
                       </div>
                     ) : (
                       <>
                         <div>
                            <label className="text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1"><FolderInput size={14} /> Đường dẫn lưu trữ</label>
                            <div className="flex gap-2">
                               <input type="text" value={savePath} onChange={(e) => setSavePath(e.target.value)} className={`w-full bg-black/30 border rounded-xl pl-3 pr-3 py-2.5 text-sm text-purple-100 font-mono outline-none ${folderError ? 'border-red-500/50' : 'border-white/10'}`} disabled/>
                               <button onClick={handleSelectFolder} className="bg-white/10 hover:bg-white/20 text-white p-2.5 rounded-xl border border-white/10"><FolderSearch size={20} /></button>
                            </div>
                            {folderError && <div className="mt-2 text-xs text-red-400 flex items-center gap-1.5"><AlertCircle size={12} /> {folderError}</div>}
                         </div>
                         <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                            <div className="flex items-center gap-4 bg-white/5 p-2 rounded-xl border border-white/10 w-full sm:w-auto justify-center sm:justify-start">
                               <label className="flex items-center gap-2 cursor-pointer group"><input type="checkbox" className="hidden" checked={downloadOptions.video} onChange={() => setDownloadOptions(prev => ({...prev, video: !prev.video}))}/><div className={`w-5 h-5 rounded-md border flex items-center justify-center ${downloadOptions.video ? 'bg-blue-600 border-blue-600' : 'border-slate-500'}`}>{downloadOptions.video && <CheckSquare size={14} />}</div><span className="text-sm text-blue-300">Videos</span></label>
                               <div className="w-px h-4 bg-white/10 mx-1"></div>
                               <label className="flex items-center gap-2 cursor-pointer group"><input type="checkbox" className="hidden" checked={downloadOptions.image} onChange={() => setDownloadOptions(prev => ({...prev, image: !prev.image}))}/><div className={`w-5 h-5 rounded-md border flex items-center justify-center ${downloadOptions.image ? 'bg-pink-600 border-pink-600' : 'border-slate-500'}`}>{downloadOptions.image && <CheckSquare size={14} />}</div><span className="text-sm text-pink-300">Images</span></label>
                            </div>
                            <button onClick={startDownload} disabled={!canDownload} className="w-full sm:w-auto flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white py-3 px-8 rounded-xl font-bold shadow-lg shadow-purple-900/40 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 group border border-white/10"><div className="flex items-center gap-2"><Download size={18} /><span>Tải xuống ngay</span></div></button>
                         </div>
                       </>
                     )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        {activeTab === 'history' && (
          <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-500">
             <div className="grid gap-4">
                {historyItems.map((item) => (
                  <div key={item.id} className="bg-white/5 backdrop-blur-md p-4 rounded-xl border border-white/10 shadow-sm flex items-start gap-4 group hover:border-purple-500/30 transition-all duration-300 hover:bg-white/10">
                    <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-lg self-start mt-1 border border-emerald-500/20"><CheckCircle2 size={24} /></div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-slate-200 truncate pr-4 text-sm sm:text-base" title={item.url}>{item.url}</h4>
                      {item.savePath && <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-black/30 p-1.5 rounded-lg mt-2 border border-white/5 w-fit font-mono"><FolderOpen size={12} className="text-amber-400"/> {item.savePath}</div>}
                      <div className="flex flex-wrap gap-x-4 gap-y-2 mt-3 text-sm text-slate-400">
                        <span className="flex items-center gap-1.5 bg-white/5 px-2 py-1 rounded-md text-xs"><Clock size={12} /> {new Date(item.timestamp).toLocaleDateString('vi-VN')}</span>
                        {item.downloadConfig?.video && <span className="flex items-center gap-1.5 text-blue-300 bg-blue-500/10 px-2 py-1 rounded-md text-xs border border-blue-500/10"><Video size={12} /> {item.videoCount}</span>}
                        {item.downloadConfig?.image && <span className="flex items-center gap-1.5 text-pink-300 bg-pink-500/10 px-2 py-1 rounded-md text-xs border border-pink-500/10"><ImageIcon size={12} /> {item.imageCount}</span>}
                      </div>
                    </div>
                    <button onClick={() => handleDeleteHistory(item.id)} className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"><Trash2 size={18} /></button>
                  </div>
                ))}
             </div>
          </div>
        )}
      </main>
    </div>
  );
}