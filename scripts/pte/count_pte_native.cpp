#include <cstdint>
#include <iostream>
#include <vector>
#include <chrono>
struct Arc { int j, t; };
int main() {
    int n, m, nk;
    std::cin >> n >> m >> nk;
    std::vector<std::vector<Arc>> out(n);
    for (int a=0; a<m; ++a) {
        int i,j,t; std::cin >> i >> j >> t; out[i].push_back({j,t});
    }
    for (int k=0; k<nk; ++k) {
        int o,d,budget; std::cin >> o >> d >> budget;
        std::vector<int64_t> remaining(n);
        for (auto& x: remaining) std::cin >> x;
        auto start=std::chrono::steady_clock::now();
        size_t lattice=size_t(budget+1)*n;
        std::vector<uint64_t> seen((lattice+63)/64,0);
        std::vector<uint32_t> queue; queue.reserve(100000);
        queue.push_back(o); seen[o/64] |= uint64_t(1)<<(o%64);
        uint64_t edges=0,sinks=0;
        for (size_t c=0;c<queue.size();++c) {
            uint32_t key=queue[c]; int t=key/n,i=key%n;
            if(i==d) ++sinks;
            for (const auto& a:out[i]) {
                int arrival=t+a.t;
                if(int64_t(arrival)+remaining[a.j]>budget) continue;
                ++edges;
                uint32_t next=uint32_t(arrival)*n+a.j;
                uint64_t mask=uint64_t(1)<<(next%64);
                if(!(seen[next/64]&mask)) {
                    seen[next/64]|=mask; queue.push_back(next);
                }
            }
        }
        double secs=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        std::cout << k << " " << queue.size() << " " << edges << " " << sinks << " " << secs << std::endl;
    }
}
