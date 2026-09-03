import { useState, useEffect, useMemo } from 'react';

interface LabResult {
  waktu_hasil?: string;
  waktu_order?: string;
  nomor_rm: string;
  nama_lengkap: string;
  parameter_tes: string;
  nilai_hasil: string;
  satuan: string;
  flag_abnormalitas?: string;
  status_hasil?: string;
}

const INSTRUMENTS = [
  { id: 'bc5150', name: 'Mindray BC-5150', fullName: 'Mindray BC-5150 (Hematologi)', port: '5100', status: 'Online' },
  { id: 'bs240', name: 'Mindray BS-240', fullName: 'Mindray BS-240 (Kimia Klinik)', port: '5101', status: 'Standby' },
  { id: 'u120', name: 'Urinalisis UA-600', fullName: 'Urinalisis UA-600', port: '5102', status: 'Offline' },
  { id: 'immuno1', name: 'Imunologi CL-900i', fullName: 'Imunologi CL-900i', port: '5103', status: 'Standby' },
  { id: 'coag1', name: 'Koagulasi CA-50', fullName: 'Koagulasi CA-50', port: '5104', status: 'Offline' },
  { id: 'electrolyte', name: 'Electrolyte Analyzer', fullName: 'Electrolyte Analyzer', port: '5105', status: 'Offline' },
  { id: 'gas1', name: 'Blood Gas Analyzer', fullName: 'Blood Gas Analyzer', port: '5106', status: 'Offline' },
  { id: 'micro1', name: 'Microbiology Reader', fullName: 'Microbiology Barcode Reader', port: '5107', status: 'Offline' },
  { id: 'sec_hema', name: 'Sysmex XN-550', fullName: 'Sysmex XN-550 (Backup Hema)', port: '5108', status: 'Offline' },
];

const RADIUS = { sm: '8px', md: '10px', lg: '14px' };
const SHADOW = '0 1px 3px rgba(15, 23, 42, 0.04)';
const COLOR = {
  bg: '#f8fafc', surface: '#ffffff', border: '#e2e8f0', borderInput: '#cbd5e1', textPrimary: '#0f172a',
  textBody: '#1e293b', textMuted: '#64748b', textSubtle: '#94a3b8', accent: '#2563eb', accentSoft: '#bfdbfe',
  accentBgSoft: '#eff6ff', accentBorderSoft: '#dbeafe', success: '#059669', danger: '#dc2626', dangerBg: '#fee2e2',
  dangerText: '#991b1b', warnBg: '#fef08a', warnText: '#854d0e', online: '#22c55e', offline: '#94a3b8',
  sidebarBg: '#0f172a', sidebarHover: '#1e293b', sidebarText: '#94a3b8', sidebarActive: '#ffffff',
};

export default function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeInstrument, setActiveInstrument] = useState(INSTRUMENTS[0].id);
  const [data, setData] = useState<LabResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Sistem siap. Menampilkan data staging instrumen.');
  const [lastSyncTime, setLastSyncTime] = useState<string>('-');

  // Filter & Pagination States
  const [searchTerm, setSearchTerm] = useState('');
  const [filterAbnormal, setFilterAbnormal] = useState('ALL');
  const [sortBy, setSortBy] = useState('newest');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(50); // Maksimal aman di 200

  // Reset page to 1 whenever search, filter, or instrument changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, filterAbnormal, sortBy, activeInstrument]);

  const fetchLabData = async (isManualSync = false) => {
    if (isManualSync) setLoading(true);
    setStatusMessage(isManualSync ? `⏳ Menyelaraskan antrean dengan ${activeInstrument}...` : 'Memuat data lokal...');

    try {
      const response = await fetch('http://127.0.0.1:8000/api/results');
      const result = await response.json();

      if (result.status === 'success') {
        setData(result.data);
        const now = new Date().toLocaleTimeString('id-ID');
        setLastSyncTime(now);
        setStatusMessage(isManualSync ? `✅ Sinkronisasi instrumen berhasil (${result.data.length} parameter).` : 'Data berhasil dimuat.');
      } else {
        setStatusMessage(`⚠️ ${result.message}`);
      }
    } catch (error) {
      setStatusMessage('❌ Gagal terhubung ke LIS Backend (Uvicorn mati atau port salah).');
    } finally {
      if (isManualSync) setLoading(false);
    }
  };

  useEffect(() => {
    fetchLabData(false);
  }, [activeInstrument]);

  const stats = useMemo(() => {
    const totalParameters = data.length;
    const uniquePatients = new Set(data.map(item => item.nomor_rm + item.nama_lengkap)).size;
    const abnormalCount = data.filter(item => item.flag_abnormalitas && item.flag_abnormalitas !== 'N').length;
    return { totalParameters, uniquePatients, abnormalCount };
  }, [data]);

  const filteredAndSortedData = useMemo(() => {
    return data
      .filter(item => {
        const matchesSearch =
          (item.nama_lengkap || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
          (item.nomor_rm || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
          (item.parameter_tes || '').toLowerCase().includes(searchTerm.toLowerCase());

        if (filterAbnormal === 'NORMAL') return matchesSearch && (!item.flag_abnormalitas || item.flag_abnormalitas === 'N');
        if (filterAbnormal === 'ABNORMAL') return matchesSearch && (item.flag_abnormalitas && item.flag_abnormalitas !== 'N');
        return matchesSearch;
      })
      .sort((a, b) => {
        if (sortBy === 'name') return (a.nama_lengkap || '').localeCompare(b.nama_lengkap || '');
        const timeA = new Date(a.waktu_hasil || a.waktu_order || 0).getTime();
        const timeB = new Date(b.waktu_hasil || b.waktu_order || 0).getTime();
        return sortBy === 'oldest' ? timeA - timeB : timeB - timeA;
      });
  }, [data, searchTerm, filterAbnormal, sortBy]);

  // PAGINATION LOGIC
  const totalItems = filteredAndSortedData.length;
  const totalPages = Math.ceil(totalItems / rowsPerPage);
  
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * rowsPerPage;
    return filteredAndSortedData.slice(startIndex, startIndex + rowsPerPage);
  }, [filteredAndSortedData, currentPage, rowsPerPage]);

  // ALGORITMA BLOCK SHIFTING (1-5, 6-10, dst)
  const paginationBlock = useMemo(() => {
    const pages = [];
    const maxVisible = 5;
    
    // Hitung halaman pembuka di blok saat ini (contoh jika currentPage = 6, maka startPage = 6)
    const startPage = Math.floor((currentPage - 1) / maxVisible) * maxVisible + 1;
    // Hitung halaman penutup di blok saat ini
    const endPage = Math.min(startPage + maxVisible - 1, totalPages);

    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }
    
    return { pages, startPage, endPage };
  }, [currentPage, totalPages]);

  const currentInstInfo = INSTRUMENTS.find(i => i.id === activeInstrument);

  const renderedTableRows = useMemo(() => {
    if (paginatedData.length === 0) {
      return (
        <tr>
          <td colSpan={7} style={{ padding: '60px', textAlign: 'center', color: COLOR.textSubtle }}>
            {data.length === 0 ? 'Basis data staging masih kosong. Lakukan transmisi data pada alat fisik lalu klik Sync Data.' : 'Data tidak ditemukan berdasarkan filter pencarian.'}
          </td>
        </tr>
      );
    }

    return paginatedData.map((item, index) => {
      const isAbnormal = item.flag_abnormalitas && item.flag_abnormalitas !== 'N';
      return (
        <tr key={index} className="lis-table-row" style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: index % 2 === 0 ? COLOR.surface : '#fafafa' }}>
          <td style={{ padding: '14px 20px', color: COLOR.textMuted }}>{item.nomor_rm}</td>
          <td style={{ padding: '14px 20px', fontWeight: '500', color: COLOR.textBody }}>{item.nama_lengkap}</td>
          <td style={{ padding: '14px 20px', color: COLOR.textMuted }}>{item.waktu_hasil ? new Date(item.waktu_hasil).toLocaleString('id-ID') : '-'}</td>
          <td style={{ padding: '14px 20px', fontWeight: '600', color: COLOR.accent }}>{item.parameter_tes}</td>
          <td style={{ padding: '14px 20px' }}>
            <span style={{ color: isAbnormal ? COLOR.danger : COLOR.textPrimary, fontWeight: isAbnormal ? 'bold' : 'normal' }}>
              {item.nilai_hasil} {isAbnormal && <span style={{ fontSize: '0.75em', backgroundColor: COLOR.dangerBg, color: COLOR.dangerText, padding: '2px 6px', borderRadius: RADIUS.sm, marginLeft: '6px', fontWeight: '700' }}>{item.flag_abnormalitas}</span>}
            </span>
          </td>
          <td style={{ padding: '14px 20px', color: COLOR.textMuted }}>{item.satuan}</td>
          <td style={{ padding: '14px 20px' }}>
            <span style={{ padding: '4px 10px', backgroundColor: COLOR.warnBg, color: COLOR.warnText, borderRadius: RADIUS.sm, fontSize: '0.8em', fontWeight: '500' }}>
              {item.status_hasil || 'Menunggu Validasi'}
            </span>
          </td>
        </tr>
      );
    });
  }, [paginatedData, data.length]);

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', backgroundColor: COLOR.bg, fontFamily: 'Inter, system-ui, sans-serif', overflow: 'hidden' }}>
      
      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes lis-spin { to { transform: rotate(360deg); } }
        .sidebar-btn { transition: all 0.15s ease; }
        .sidebar-btn:hover { background-color: ${COLOR.sidebarHover}; color: ${COLOR.sidebarActive}; }
        .topbar-btn:hover { background-color: #f1f5f9; }
        .lis-sync-btn:hover:not(:disabled) { background-color: ${COLOR.accentBgSoft}; }
        .lis-input:focus, .lis-select:focus { outline: none; border-color: #93c5fd; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12); }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
        .hamburger-btn { transition: background-color 0.2s ease, transform 0.15s ease; }
        .hamburger-btn:active { transform: scale(0.9); }
        .hamburger-bar { transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.18s ease; transform-origin: center; will-change: transform; }
        
        /* Interactive Pagination Styles */
        .page-btn { transition: all 0.2s; border: 1px solid ${COLOR.borderInput}; background: white; color: ${COLOR.textBody}; border-radius: 6px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .page-btn:hover:not(:disabled) { background: #f1f5f9; border-color: #94a3b8; }
        .page-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .page-num-btn { transition: all 0.2s; border: 1px solid ${COLOR.borderInput}; background: white; color: ${COLOR.textBody}; border-radius: 6px; min-width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 500; cursor: pointer; padding: 0 8px; }
        .page-num-btn:hover:not(.active) { background: #f1f5f9; border-color: #94a3b8; }
        .page-num-btn.active { background: ${COLOR.accent}; color: white; border-color: ${COLOR.accent}; cursor: default; }
      `}</style>

      <aside style={{ 
        width: '260px', marginLeft: isSidebarOpen ? '0' : '-260px', backgroundColor: COLOR.sidebarBg, 
        transition: 'margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1)', flexShrink: 0, display: 'flex', flexDirection: 'column', zIndex: 20
      }}>
        <div style={{ padding: '24px', borderBottom: '1px solid #1e293b' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: COLOR.accent, borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            </div>
            <div>
              <h2 style={{ color: 'white', fontSize: '18px', fontWeight: '700', letterSpacing: '-0.02em' }}>LIS Server</h2>
              <p style={{ color: COLOR.sidebarText, fontSize: '12px' }}>Marina Permata</p>
            </div>
          </div>
        </div>

        <div className="custom-scrollbar" style={{ padding: '16px 12px', flex: 1, overflowY: 'auto' }}>
          <p style={{ fontSize: '11px', fontWeight: '600', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px', paddingLeft: '12px' }}>Daftar Instrumen</p>
          
          {INSTRUMENTS.map((inst) => {
            const isActive = inst.id === activeInstrument;
            return (
              <button key={inst.id} onClick={() => setActiveInstrument(inst.id)} className="sidebar-btn" style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 12px',
                  backgroundColor: isActive ? COLOR.sidebarHover : 'transparent', color: isActive ? COLOR.sidebarActive : COLOR.sidebarText,
                  border: 'none', borderRadius: RADIUS.md, cursor: 'pointer', textAlign: 'left', marginBottom: '4px'
                }}>
                <span style={{ 
                  height: '8px', width: '8px', borderRadius: '50%', flexShrink: 0,
                  backgroundColor: inst.status === 'Online' ? COLOR.online : inst.status === 'Standby' ? '#eab308' : COLOR.offline, 
                  boxShadow: isActive && inst.status === 'Online' ? '0 0 6px #22c55e' : 'none'
                }}></span>
                <span style={{ fontSize: '13px', fontWeight: isActive ? '600' : '400', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{inst.name}</span>
              </button>
            );
          })}
        </div>
      </aside>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={{ height: '64px', backgroundColor: COLOR.surface, borderBottom: `1px solid ${COLOR.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px', zIndex: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button className="topbar-btn hamburger-btn" onClick={() => setIsSidebarOpen(!isSidebarOpen)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '10px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: COLOR.textBody }}>
              <span style={{ position: 'relative', width: '20px', height: '16px', display: 'inline-block' }}>
                <span className="hamburger-bar" style={{ position: 'absolute', left: 0, top: '7px', width: '20px', height: '2px', borderRadius: '2px', backgroundColor: COLOR.textBody, transform: isSidebarOpen ? 'translateY(0) rotate(45deg)' : 'translateY(-7px) rotate(0deg)' }}></span>
                <span className="hamburger-bar" style={{ position: 'absolute', left: 0, top: '7px', width: '20px', height: '2px', borderRadius: '2px', backgroundColor: COLOR.textBody, opacity: isSidebarOpen ? 0 : 1, transform: isSidebarOpen ? 'scaleX(0)' : 'scaleX(1)' }}></span>
                <span className="hamburger-bar" style={{ position: 'absolute', left: 0, top: '7px', width: '20px', height: '2px', borderRadius: '2px', backgroundColor: COLOR.textBody, transform: isSidebarOpen ? 'translateY(0) rotate(-45deg)' : 'translateY(7px) rotate(0deg)' }}></span>
              </span>
            </button>
            <h1 style={{ fontSize: '18px', fontWeight: '600', color: COLOR.textPrimary }}>{currentInstInfo?.fullName}</h1>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '12px', fontWeight: '600', color: COLOR.textBody }}>Port {currentInstInfo?.port}</span>
              <span style={{ fontSize: '11px', color: COLOR.textMuted }}>Terakhir Sinkron: {lastSyncTime}</span>
            </div>
            <button onClick={() => fetchLabData(true)} disabled={loading} className="lis-sync-btn" style={{ background: 'transparent', color: COLOR.accent, border: `1px solid ${COLOR.accentSoft}`, padding: '8px 16px', borderRadius: RADIUS.md, cursor: 'pointer', fontSize: '13px', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ animation: loading ? 'lis-spin 1s linear infinite' : 'none' }}>
                <polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
              </svg>
              {loading ? 'Syncing...' : 'Sync Data'}
            </button>
          </div>
        </header>

        <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto', padding: '32px', backgroundColor: COLOR.bg }}>
          <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
            
            <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderLeft: '4px solid #0ea5e9', padding: '16px 20px', borderRadius: RADIUS.md, marginBottom: '24px', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: '2px' }}><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
              <div>
                <div style={{ color: '#0369a1', fontSize: '14px', fontWeight: '600', marginBottom: '4px' }}>Prosedur Penarikan Data</div>
                <div style={{ color: '#0c4a6e', fontSize: '13px', lineHeight: '1.6' }}>
                  <strong>1.</strong> Pastikan alat fisik <strong>{currentInstInfo?.name}</strong> dalam keadaan <em>Standby</em>.<br />
                  <strong>2.</strong> Tekan tombol <strong>"Comm. All / Send"</strong> pada layar alat.<br />
                  <strong>3.</strong> Klik tombol <strong>"Sync Data"</strong> di kanan atas layar untuk merefresh tabel.
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px', marginBottom: '24px' }}>
              <div style={{ background: COLOR.surface, padding: '24px', borderRadius: RADIUS.lg, border: `1px solid ${COLOR.border}`, boxShadow: SHADOW }}>
                <div style={{ color: COLOR.textMuted, fontSize: '13px', fontWeight: '500' }}>Parameter Terbaca</div>
                <div style={{ fontSize: '32px', fontWeight: '700', marginTop: '8px', color: COLOR.textPrimary, letterSpacing: '-0.02em' }}>{stats.totalParameters}</div>
              </div>
              <div style={{ background: COLOR.surface, padding: '24px', borderRadius: RADIUS.lg, border: `1px solid ${COLOR.border}`, boxShadow: SHADOW }}>
                <div style={{ color: COLOR.textMuted, fontSize: '13px', fontWeight: '500' }}>Estimasi Pasien</div>
                <div style={{ fontSize: '32px', fontWeight: '700', marginTop: '8px', color: COLOR.textPrimary, letterSpacing: '-0.02em' }}>{stats.uniquePatients}</div>
              </div>
              <div style={{ background: COLOR.surface, padding: '24px', borderRadius: RADIUS.lg, border: `1px solid ${COLOR.border}`, boxShadow: SHADOW }}>
                <div style={{ color: COLOR.textMuted, fontSize: '13px', fontWeight: '500' }}>Flag Abnormal (H/L)</div>
                <div style={{ fontSize: '32px', fontWeight: '700', color: COLOR.danger, marginTop: '8px', letterSpacing: '-0.02em' }}>{stats.abnormalCount}</div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
              <div style={{ position: 'relative', flex: '1', minWidth: '300px' }}>
                <span style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: COLOR.textSubtle, display: 'flex' }}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg></span>
                <input type="text" placeholder="Cari nama pasien, rekam medis, atau tes..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="lis-input" style={{ width: '100%', padding: '12px 16px 12px 46px', borderRadius: RADIUS.md, border: `1px solid ${COLOR.borderInput}`, fontSize: '14px', background: COLOR.surface, color: COLOR.textBody }} />
              </div>
              <select value={filterAbnormal} onChange={(e) => setFilterAbnormal(e.target.value)} className="lis-select" style={{ padding: '12px 16px', borderRadius: RADIUS.md, border: `1px solid ${COLOR.borderInput}`, backgroundColor: COLOR.surface, color: COLOR.textBody, fontSize: '14px', cursor: 'pointer' }}>
                <option value="ALL">Filter: Semua</option>
                <option value="NORMAL">Filter: Normal</option>
                <option value="ABNORMAL">Filter: Abnormal (H/L)</option>
              </select>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="lis-select" style={{ padding: '12px 16px', borderRadius: RADIUS.md, border: `1px solid ${COLOR.borderInput}`, backgroundColor: COLOR.surface, color: COLOR.textBody, fontSize: '14px', cursor: 'pointer' }}>
                <option value="newest">Urut: Terbaru</option>
                <option value="oldest">Urut: Terlama</option>
                <option value="name">Urut: Nama (A-Z)</option>
              </select>
            </div>

            {/* TABEL DATA */}
            <div style={{ background: COLOR.surface, borderRadius: RADIUS.lg, boxShadow: SHADOW, border: `1px solid ${COLOR.border}` }}>
              <div className="custom-scrollbar" style={{ overflowX: 'auto', minHeight: '300px' }}>
                <table style={{ width: '100%', minWidth: '900px', tableLayout: 'fixed', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
                  <thead style={{ backgroundColor: COLOR.bg, color: '#475569', borderBottom: `1px solid ${COLOR.border}` }}>
                    <tr>
                      <th style={{ width: '12%', padding: '16px 20px', fontWeight: '600' }}>No. RM</th>
                      <th style={{ width: '22%', padding: '16px 20px', fontWeight: '600' }}>Nama Pasien</th>
                      <th style={{ width: '15%', padding: '16px 20px', fontWeight: '600' }}>Waktu</th>
                      <th style={{ width: '12%', padding: '16px 20px', fontWeight: '600' }}>Parameter</th>
                      <th style={{ width: '14%', padding: '16px 20px', fontWeight: '600' }}>Hasil</th>
                      <th style={{ width: '10%', padding: '16px 20px', fontWeight: '600' }}>Satuan</th>
                      <th style={{ width: '15%', padding: '16px 20px', fontWeight: '600' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {renderedTableRows}
                  </tbody>
                </table>
              </div>
              
              {/* KONTROL PAGINASI INTERAKTIF BLOCK SHIFTING */}
              {totalItems > 0 && (
                <div style={{ padding: '16px 20px', borderTop: `1px solid ${COLOR.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', backgroundColor: COLOR.surface, borderBottomLeftRadius: RADIUS.lg, borderBottomRightRadius: RADIUS.lg }}>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '13px', color: COLOR.textMuted }}>Baris per halaman:</span>
                    <select 
                      value={rowsPerPage} 
                      onChange={(e) => { setRowsPerPage(Number(e.target.value)); setCurrentPage(1); }}
                      className="lis-select"
                      style={{ padding: '6px 10px', borderRadius: '6px', border: `1px solid ${COLOR.borderInput}`, fontSize: '13px', backgroundColor: COLOR.bg, cursor: 'pointer', outline: 'none' }}
                    >
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                      <option value={200}>200</option>
                    </select>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <span style={{ fontSize: '13px', color: COLOR.textMuted }}>
                      Data <strong style={{ color: COLOR.textBody }}>{((currentPage - 1) * rowsPerPage) + 1} - {Math.min(currentPage * rowsPerPage, totalItems)}</strong> dari <strong style={{ color: COLOR.textBody }}>{totalItems}</strong>
                    </span>
                    
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button 
                        className="page-btn" 
                        disabled={currentPage === 1} 
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        title="Halaman Sebelumnya"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
                      </button>

                      {/* Indikator Elipsis Kiri (Jika blok angka melompat ke depan) */}
                      {paginationBlock.startPage > 1 && (
                        <button className="page-num-btn" onClick={() => setCurrentPage(paginationBlock.startPage - 1)}>
                          ...
                        </button>
                      )}

                      {/* Nomor Halaman Dinamis (Blok) */}
                      {paginationBlock.pages.map(page => (
                        <button
                          key={page}
                          className={`page-num-btn ${currentPage === page ? 'active' : ''}`}
                          onClick={() => setCurrentPage(page)}
                        >
                          {page}
                        </button>
                      ))}

                      {/* Indikator Elipsis Kanan (Jika masih ada sisa halaman setelah blok saat ini) */}
                      {paginationBlock.endPage < totalPages && (
                        <button className="page-num-btn" onClick={() => setCurrentPage(paginationBlock.endPage + 1)}>
                          ...
                        </button>
                      )}

                      <button 
                        className="page-btn" 
                        disabled={currentPage === totalPages || totalPages === 0} 
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        title="Halaman Berikutnya"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                      </button>
                    </div>
                  </div>

                </div>
              )}
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}