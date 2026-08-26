import { useState, useEffect } from 'react';
import type { LabResult } from './types/lab';

function App() {
  const [results, setResults] = useState<LabResult[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/results')
      .then(response => {
        if (!response.ok) {
          throw new Error('Gagal terhubung ke API LIS');
        }
        return response.json();
      })
      .then(data => {
        // TypeScript tahu bahwa data.data adalah sekumpulan LabResult
        setResults(data.data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: '20px' }}>Memuat data dari instrumen...</div>;
  if (error) return <div style={{ padding: '20px', color: 'red' }}>Error: {error}</div>;

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
      <h2>Dashboard Hasil Laboratorium</h2>
      
      <table border={1} cellPadding={10} style={{ borderCollapse: 'collapse', width: '100%', textAlign: 'left' }}>
        <thead style={{ backgroundColor: '#f3f4f6' }}>
          <tr>
            <th>No. RM</th>
            <th>Pasien</th>
            <th>Waktu Order</th>
            <th>Parameter</th>
            <th>Hasil</th>
            <th>Satuan</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {results.map((item, index) => (
            <tr key={index}>
              <td>{item.nomor_rm}</td>
              <td>{item.nama_lengkap}</td>
              <td>{new Date(item.waktu_order).toLocaleString('id-ID')}</td>
              <td><strong>{item.parameter_tes}</strong></td>
              <td>
                <span style={{ 
                  color: item.flag_abnormalitas && item.flag_abnormalitas !== 'N' ? '#dc2626' : 'inherit',
                  fontWeight: item.flag_abnormalitas && item.flag_abnormalitas !== 'N' ? 'bold' : 'normal'
                }}>
                  {item.nilai_hasil} {item.flag_abnormalitas && item.flag_abnormalitas !== 'N' ? `(${item.flag_abnormalitas})` : ''}
                </span>
              </td>
              <td>{item.satuan}</td>
              <td>
                <span style={{ padding: '4px 8px', backgroundColor: '#fef08a', borderRadius: '4px', fontSize: '0.85em' }}>
                  {item.status_hasil}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;