import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePatients, useCreatePatient } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Search, UserPlus } from 'lucide-react';

export default function Patients() {
  const { data: patients = [], isLoading } = usePatients();
  const createPatient = useCreatePatient();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', age: '', sex: 'female' as 'male' | 'female' | 'other', mrn: '' });
  const [createError, setCreateError] = useState<string | null>(null);

  const filtered = patients.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.mrn.toLowerCase().includes(search.toLowerCase())
  );

  const handleCreate = async () => {
    setCreateError(null);
    const age = Number(form.age);
    if (!form.name.trim()) { setCreateError('Name is required.'); return; }
    if (!age || age <= 0 || age > 120) { setCreateError('Enter a valid age (1-120).'); return; }
    try {
      const patient = await createPatient.mutateAsync({ name: form.name.trim(), age, sex: form.sex, mrn: form.mrn.trim() || undefined });
      setShowCreate(false);
      setForm({ name: '', age: '', sex: 'female', mrn: '' });
      navigate(`/patients/${patient.id}`);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Could not create patient.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Patients</h1>
        <div className="flex space-x-2">
          <Button variant="outline" onClick={() => setShowCreate(s => !s)}>
            <UserPlus className="w-4 h-4 mr-2" /> New Patient
          </Button>
          <Button onClick={() => navigate('/analysis/new')}>New Analysis</Button>
        </div>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle>New Patient</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {createError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-md text-sm">{createError}</div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Name</label>
                <input className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Age</label>
                <input type="number" className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" value={form.age}
                  onChange={e => setForm(f => ({ ...f, age: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Sex</label>
                <select className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" value={form.sex}
                  onChange={e => setForm(f => ({ ...f, sex: e.target.value as any }))}>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">MRN (optional)</label>
                <input className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm" value={form.mrn}
                  onChange={e => setForm(f => ({ ...f, mrn: e.target.value }))} placeholder="auto-generated if blank" />
              </div>
            </div>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={createPatient.isPending}>
                {createPatient.isPending ? 'Creating…' : 'Create Patient'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <Search className="w-5 h-5 text-slate-400" />
            <input 
              type="text" 
              placeholder="Search by name or MRN..." 
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="flex-1 border-none focus:ring-0 text-sm bg-transparent outline-none"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-slate-500">Loading patients...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-50 text-slate-500 border-y border-slate-200">
                  <tr>
                    <th className="px-6 py-3 font-medium">Patient</th>
                    <th className="px-6 py-3 font-medium">Age / Sex</th>
                    <th className="px-6 py-3 font-medium">Last Analysis</th>
                    <th className="px-6 py-3 font-medium">Overall Risk</th>
                    <th className="px-6 py-3 font-medium">Modalities</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {filtered.map(p => (
                    <tr 
                      key={p.id} 
                      onClick={() => navigate(`/patients/${p.id}`)}
                      className="hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div className="font-medium text-slate-900">{p.name}</div>
                        <div className="text-slate-500 text-xs">{p.mrn}</div>
                      </td>
                      <td className="px-6 py-4 text-slate-600 capitalize">
                        {p.age} • {p.sex}
                      </td>
                      <td className="px-6 py-4 text-slate-600">
                        {p.lastAnalysisAt ? new Date(p.lastAnalysisAt).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="px-6 py-4">
                        {p.currentRisk ? (
                          <Badge variant={p.currentRisk === 'high' ? 'destructive' : p.currentRisk === 'review_required' ? 'warning' : 'secondary'}>
                            {p.currentRisk.toUpperCase()}
                          </Badge>
                        ) : '-'}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex space-x-1">
                          <Badge variant="outline" className="text-[10px]">{p.availableModalities.length}/6</Badge>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
