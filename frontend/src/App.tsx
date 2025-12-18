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

const API_URL = 'http://localhost:8000';

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [names, setNames] = useState<Name[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  useEffect(() => {
    if (currentUser) {
      fetchRecommendations();
    }
  }, [currentUser]);

  const fetchUsers = async () => {
    try {
      const res = await axios.get(`${API_URL}/users`);
      setUsers(res.data);
    } catch (err) {
      console.error(err);
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
          <span className="font-bold text-xl text-pink-500">BabyTinder</span>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={async () => {
              setLoading(true);
              try {
                const res = await axios.post(`${API_URL}/generate`);
                alert(res.data.message || "Generated!");
                fetchRecommendations();
              } catch (e) {
                alert("Generation failed (check console/logs for API Key errors)");
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

      {/* Main Swiper */}
      <div className="flex-1 flex flex-col items-center justify-center p-4 relative">
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
                onSwipe={index === 1 ? handleSwipe : () => { }}
              />
            ))}
            {/* The top card is simply the last one in this reversed slice, if we render them stacked. 
                But SwipeCard is absolute. 
                Wait, key issue: Logic above is slightly flawed for stacking. 
                The 'top' card should be the first in `names` array.
                If I render `names[0]`, it's on top.
                But if I map, the last element rendered is on top physically in DOM (z-index).
                So I want `names[0]` to be last in DOM list.
            */}
          </div>
        ) : (
          <div className="text-center">
            <h2 className="text-2xl font-bold text-gray-700 mb-2">No more names!</h2>
            <p className="text-gray-500">Check back later or generate more.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
