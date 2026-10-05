import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePatients } from '@/features/hooks';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Search } from 'lucide-react';

export default function Patients() {
  const { data: patients = [], isLoading } = usePatients();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  const filtered = patients.filter(p => 
    p.name.toLowerCase().includes(search.toLowerCase()) || 
    p.mrn.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Patients</h1>
        <Button onClick={() => navigate('/analysis/new')}>New Analysis</Button>
      </div>

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
                          <Badge variant="outline" className="text-[10px]">{p.availableModalities.length}/5</Badge>
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
