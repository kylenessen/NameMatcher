import { useState, useEffect } from 'react';
import axios from 'axios';
import { SwipeCard } from './components/SwipeCard';
import { Users, RefreshCw } from 'lucide-react';

interface User {
  id: number;
  name: string;
}

interface Name {
  id: number;
  name: string;
  gender?: string;
  origin?: string;
  meaning?: string;
}

const API_URL = '/api';

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [names, setNames] = useState<Name[]>([]);
  const [loading, setLoading] = useState(false);

  const [view, setView] = useState<'swipe' | 'matches'>('swipe');

  /* Dashboard State */
  const [dashboard, setDashboard] = useState<{
    matches: Name[];
    kyle_likes: Name[];
    emily_likes: Name[];
    rejected: Name[];
  } | null>(null);

  useEffect(() => {
    fetchUsers();
  }, []);

  useEffect(() => {
    if (currentUser) {
      fetchRecommendations();
    }
  }, [currentUser]);

  useEffect(() => {
    if (view === 'matches') {
      fetchDashboard();
    }
  }, [view]);

  const fetchUsers = async () => {
    try {
      const res = await axios.get(`${API_URL}/users`);
      setUsers(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchDashboard = async () => {
    try {
      const res = await axios.get(`${API_URL}/dashboard`);
      setDashboard(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchRecommendations = async () => {
    if (!currentUser) return;
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/recommendations/${currentUser.id}`);
      setNames(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSwipe = async (direction: 'like' | 'dislike' | 'maybe') => {
    if (!currentUser || names.length === 0) return;

    const currentName = names[0];

    try {
      await axios.post(`${API_URL}/swipe`, {
        user_id: currentUser.id,
        name_id: currentName.id,
        decision: direction
      });

      // Remove swiped name
      setNames(prev => prev.slice(1));

      // Fetch more if low
      if (names.length < 3) {
        fetchRecommendations();
      }
    } catch (err) {
      console.error("Failed to submit swipe", err);
    }
  };

  if (!currentUser) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-pink-500 to-orange-400 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl p-8 shadow-2xl max-w-md w-full text-center">
          <div className="flex justify-center mb-6">
            <div className="bg-pink-100 p-4 rounded-full">
              <Users size={48} className="text-pink-500" />
            </div>
          </div>
          <h1 className="text-3xl font-bold mb-2">Who is swiping?</h1>
          <p className="text-gray-500 mb-8">Select your profile to start discovering names.</p>

          <div className="space-y-4">
            {users.map(user => (
              <button
                key={user.id}
                onClick={() => setCurrentUser(user)}
                className="w-full py-4 px-6 rounded-xl border-2 border-gray-100 hover:border-pink-500 hover:bg-pink-50 transition-all font-semibold text-lg flex items-center justify-between group"
              >
                {user.name}
                <span className="opacity-0 group-hover:opacity-100 text-pink-500">→</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 flex justify-between items-center bg-white shadow-sm z-10">
        <div className="flex items-center gap-2">
          <span className="font-bold text-xl text-pink-500">NameMatch</span>
          <div className="flex bg-gray-100 rounded-lg p-1 ml-4">
            <button
              onClick={() => setView('swipe')}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${view === 'swipe' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-900'}`}
            >
              Swipe
            </button>
            <button
              onClick={() => setView('matches')}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${view === 'matches' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-900'}`}
            >
              Matches
            </button>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={async () => {
              setLoading(true);
              try {
                const res = await axios.post(`${API_URL}/generate`);
                alert(res.data.message);
                fetchRecommendations();
              } catch (e: any) {
                const msg = e.response?.data?.detail || e.message || "Unknown error";
                alert(`Generation failed: ${msg}`);
                console.error(e);
              } finally {
                setLoading(false);
              }
            }}
            className="px-3 py-1 bg-purple-100 text-purple-600 rounded-full hover:bg-purple-200 font-medium text-sm transition-colors flex items-center gap-1"
          >
            <span>✨</span> Generate
          </button>
          <span className="font-medium text-gray-700">{currentUser.name}</span>
          <button
            onClick={() => setCurrentUser(null)}
            className="text-sm text-gray-400 hover:text-gray-600 underline"
          >
            Switch
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col items-center justify-center p-4 relative overflow-y-auto">
        {view === 'swipe' ? (
          <div className="h-full w-full flex flex-col items-center justify-center">
            {loading && names.length === 0 ? (
              <div className="animate-spin text-pink-500">
                <RefreshCw size={32} />
              </div>
            ) : names.length > 0 ? (
              <div className="relative w-full max-w-sm h-96">
                {names.slice(0, 2).reverse().map((name, index) => (
                  <SwipeCard
                    key={name.id}
                    name={name.name}
                    onSwipe={index === Math.min(names.length, 2) - 1 ? handleSwipe : () => { }}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center">
                <h2 className="text-2xl font-bold text-gray-700 mb-2">No more names!</h2>
                <p className="text-gray-500">Check back later or generate more.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 w-full max-w-6xl p-4 overflow-y-auto">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 h-full">
              {/* Matches */}
              <div className="bg-white rounded-xl shadow-sm border border-pink-100 flex flex-col">
                <div className="p-4 border-b border-gray-50 bg-pink-50 rounded-t-xl">
                  <h3 className="font-bold text-gray-800 flex items-center gap-2">
                    <span>💖</span> Matches
                  </h3>
                </div>
                <div className="p-4 flex-1 overflow-y-auto space-y-2">
                  {dashboard?.matches.map(n => (
                    <div key={n.id} className="p-2 bg-pink-100 text-pink-700 rounded-lg font-medium text-center">{n.name}</div>
                  ))}
                  {dashboard?.matches.length === 0 && <span className="text-gray-400 text-sm">No matches yet</span>}
                </div>
              </div>

              {/* Kyle Likes */}
              <div className="bg-white rounded-xl shadow-sm border border-blue-100 flex flex-col">
                <div className="p-4 border-b border-gray-50 bg-blue-50 rounded-t-xl">
                  <h3 className="font-bold text-gray-800 flex items-center gap-2">
                    <span>👦</span> Kyle Likes
                  </h3>
                </div>
                <div className="p-4 flex-1 overflow-y-auto space-y-2">
                  {dashboard?.kyle_likes.map(n => (
                    <div key={n.id} className="p-2 bg-blue-50 text-blue-700 rounded-lg font-medium text-center">{n.name}</div>
                  ))}
                </div>
              </div>

              {/* Emily Likes */}
              <div className="bg-white rounded-xl shadow-sm border border-purple-100 flex flex-col">
                <div className="p-4 border-b border-gray-50 bg-purple-50 rounded-t-xl">
                  <h3 className="font-bold text-gray-800 flex items-center gap-2">
                    <span>👧</span> Emily Likes
                  </h3>
                </div>
                <div className="p-4 flex-1 overflow-y-auto space-y-2">
                  {dashboard?.emily_likes.map(n => (
                    <div key={n.id} className="p-2 bg-purple-50 text-purple-700 rounded-lg font-medium text-center">{n.name}</div>
                  ))}
                </div>
              </div>

              {/* Rejected */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col opacity-60">
                <div className="p-4 border-b border-gray-50 bg-gray-100 rounded-t-xl">
                  <h3 className="font-bold text-gray-800 flex items-center gap-2">
                    <span>🗑️</span> Rejected
                  </h3>
                </div>
                <div className="p-4 flex-1 overflow-y-auto space-y-2">
                  {dashboard?.rejected.map(n => (
                    <div key={n.id} className="p-2 bg-gray-50 text-gray-500 rounded-lg font-medium text-center line-through">{n.name}</div>
                  ))}
                </div>
              </div>
            </div>

            <div className="text-center mt-4 text-gray-400 text-sm">
              Swipe on "My Likes" recursively to strengthen preference!
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
