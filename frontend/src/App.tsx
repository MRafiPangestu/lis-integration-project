import { useState, useMemo } from 'react';

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

export default function App() {
  const [data, setData] = useState<LabResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Tekan tombol di bawah untuk menyinkronkan data dari antrean mesin.');
  
  const [searchTerm, setSearchTerm] = useState('');
  const [filterAbnormal, setFilterAbnormal] = useState('ALL');
  const [sortBy, setSortBy] = useState('newest');

  const handleSync = async () => {
    setLoading(true);
    setStatusMessage('⏳ Menghubungkan ke antrean staging mesin...');

    try {
      const response = await fetch('http://127.0.0.1:8000/api/results');
      const result = await response.json();

      if (result.status === 'success') {
        setData(result.data);
        setStatusMessage(`✅ Berhasil memuat ${result.data.length} total baris data.`);
      } else {
        setStatusMessage(`⚠️ ${result.message}`);
      }
    } catch (error) {
      setStatusMessage('❌ Gagal terhubung ke LIS Backend. Pastikan uvicorn menyala.');
    } finally {
      setLoading(false);
    }
  };

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
        if (sortBy === 'name') {
          return (a.nama_lengkap || '').localeCompare(b.nama_lengkap || '');
        }
        const timeA = new Date(a.waktu_hasil || a.waktu_order || 0).getTime();
        const timeB = new Date(b.waktu_hasil || b.waktu_order || 0).getTime();
        
        if (sortBy === 'oldest') return timeA - timeB;
        return timeB - timeA; // newest
      });
  }, [data, searchTerm, filterAbnormal, sortBy]);

  return (
    <div style={{ padding: '30px', fontFamily: 'Inter, system-ui, sans-serif', maxWidth: '1200px', margin: '0 auto', backgroundColor: '#f8fafc', minHeight: '100vh' }}>
      
      <div style={{ background: '#ffffff', padding: '25px', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', marginBottom: '20px', border: '1px solid #e2e8f0' }}>
        <h2 style={{ color: '#1e293b', margin: '0 0 8px 0' }}>Dashboard LIS - Simulasi Mindray BC-5150</h2>
        <p style={{ color: '#64748b', fontSize: '14px', marginBottom: '20px' }}>
          Panel kontrol manajemen seluruh hasil tes laboratorium (Full Database Sync) untuk Head IT.
        </p>

        <div style={{ display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={handleSync}
            disabled={loading}
            style={{
              backgroundColor: loading ? '#94a3b8' : '#2563eb',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              fontSize: '14px',
              fontWeight: '600',
              borderRadius: '8px',
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 2px 4px rgba(37, 99, 235, 0.2)'
            }}
          >
            {loading ? 'Memuat...' : '🔄 Sinkronisasi Semua Data'}
          </button>
          <span style={{ fontSize: '14px', fontWeight: '500', color: '#334155' }}>
            {statusMessage}
          </span>
        </div>
      </div>

      {data.length > 0 && (
        <div style={{ display: 'flex', gap: '15px', marginBottom: '20px', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="🔍 Cari Pasien, No. RM, atau Parameter..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ padding: '10px 14px', borderRadius: '8px', border: '1px solid #cbd5e1', flex: '1', minWidth: '250px', fontSize: '14px' }}
          />

          <select
            value={filterAbnormal}
            onChange={(e) => setFilterAbnormal(e.target.value)}
            style={{ padding: '10px 14px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: 'white', fontSize: '14px' }}
          >
            <option value="ALL">Semua Status Flag</option>
            <option value="NORMAL">Normal (N)</option>
            <option value="ABNORMAL">Abnormal (H/L)</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            style={{ padding: '10px 14px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: 'white', fontSize: '14px' }}
          >
            <option value="newest">Urutkan: Terbaru</option>
            <option value="oldest">Urutkan: Terlama</option>
            <option value="name">Urutkan: Nama Pasien (A-Z)</option>
          </select>
        </div>
      )}

      <div style={{ background: '#ffffff', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', overflow: 'hidden', border: '1px solid #e2e8f0' }}>
        <div style={{ overflowX: 'auto', maxHeight: '600px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
            <thead style={{ backgroundColor: '#f1f5f9', color: '#475569', position: 'sticky', top: 0, zIndex: 10 }}>
              <tr>
                <th style={{ padding: '14px' }}>No. RM</th>
                <th style={{ padding: '14px' }}>Nama Pasien</th>
                <th style={{ padding: '14px' }}>Waktu Hasil</th>
                <th style={{ padding: '14px' }}>Parameter</th>
                <th style={{ padding: '14px' }}>Hasil</th>
                <th style={{ padding: '14px' }}>Satuan</th>
                <th style={{ padding: '14px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedData.length > 0 ? (
                filteredAndSortedData.map((item, index) => {
                  const isAbnormal = item.flag_abnormalitas && item.flag_abnormalitas !== 'N';
                  return (
                    <tr key={index} style={{ borderBottom: '1px solid #f1f5f9', backgroundColor: index % 2 === 0 ? '#ffffff' : '#fafafa' }}>
                      <td style={{ padding: '14px', color: '#64748b' }}>{item.nomor_rm}</td>
                      <td style={{ padding: '14px', fontWeight: '500', color: '#1e293b' }}>{item.nama_lengkap}</td>
                      <td style={{ padding: '14px', color: '#64748b' }}>
                        {item.waktu_hasil ? new Date(item.waktu_hasil).toLocaleString('id-ID') : '-'}
                      </td>
                      <td style={{ padding: '14px', fontWeight: '600', color: '#2563eb' }}>{item.parameter_tes}</td>
                      <td style={{ padding: '14px' }}>
                        <span style={{ 
                          color: isAbnormal ? '#dc2626' : '#0f172a',
                          fontWeight: isAbnormal ? 'bold' : 'normal'
                        }}>
                          {item.nilai_hasil} {isAbnormal && <span style={{ fontSize: '0.8em', backgroundColor: '#fee2e2', color: '#991b1b', padding: '2px 6px', borderRadius: '4px', marginLeft: '6px' }}>{item.flag_abnormalitas}</span>}
                        </span>
                      </td>
                      <td style={{ padding: '14px', color: '#64748b' }}>{item.satuan}</td>
                      <td style={{ padding: '14px' }}>
                        <span style={{ padding: '4px 10px', backgroundColor: '#fef08a', color: '#854d0e', borderRadius: '6px', fontSize: '0.85em', fontWeight: '500' }}>
                          {item.status_hasil || 'Menunggu Validasi'}
                        </span>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                    {data.length === 0 ? 'Belum ada data. Silakan klik tombol "Sinkronisasi Semua Data" di atas.' : 'Tidak ada data yang cocok dengan pencarian atau filter Anda.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}