/*
 * wwfast.c — a sparse Wireworld stepper for large grids.
 *
 * Same rule as ww_cells.step: a head becomes a tail, a tail becomes a
 * conductor, and a conductor becomes a head when exactly 1 or 2 of its 8
 * neighbours are heads. Only cells next to a head can change into one, so
 * each tick costs time proportional to the number of heads, not the area.
 * wwfast.py cross-checks it cell for cell against the Python reference.
 *
 * States: 0 empty, 1 head, 2 tail, 3 conductor.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    int64_t w, h;
    uint8_t *g;         /* state per cell */
    uint8_t *cnt;       /* head-neighbour count scratch, kept at 0 between ticks */
    int64_t *heads, *tails, *touch, *nheads;
    int64_t nh, nt, cap;
} WW;

static int grow(WW *s, int64_t need) {
    if (need <= s->cap) return 0;
    int64_t cap = s->cap ? s->cap : 1024;
    while (cap < need) cap *= 2;
    int64_t *a = realloc(s->heads, cap * sizeof(int64_t));
    int64_t *b = realloc(s->tails, cap * sizeof(int64_t));
    int64_t *c = realloc(s->touch, 8 * cap * sizeof(int64_t));
    int64_t *d = realloc(s->nheads, 8 * cap * sizeof(int64_t));
    if (!a || !b || !c || !d) return -1;
    s->heads = a; s->tails = b; s->touch = c; s->nheads = d; s->cap = cap;
    return 0;
}

WW *ww_new(int64_t w, int64_t h, const uint8_t *cells) {
    WW *s = calloc(1, sizeof(WW));
    if (!s) return NULL;
    s->w = w; s->h = h;
    s->g = malloc((size_t)(w * h));
    s->cnt = calloc((size_t)(w * h), 1);
    if (!s->g || !s->cnt) return NULL;
    memcpy(s->g, cells, (size_t)(w * h));
    int64_t nh = 0, nt = 0;
    for (int64_t i = 0; i < w * h; i++) {
        if (s->g[i] == 1) nh++;
        else if (s->g[i] == 2) nt++;
    }
    if (grow(s, (nh > nt ? nh : nt) + 16)) return NULL;
    for (int64_t i = 0; i < w * h; i++) {
        if (s->g[i] == 1) s->heads[s->nh++] = i;
        else if (s->g[i] == 2) s->tails[s->nt++] = i;
    }
    return s;
}

void ww_free(WW *s) {
    if (!s) return;
    free(s->g); free(s->cnt); free(s->heads); free(s->tails);
    free(s->touch); free(s->nheads); free(s);
}

/* Advance n ticks. probes: cell indices; after each tick, every probe that is
 * a head is reported as (tick, probe number) into out (pairs). Returns the
 * number of pairs written, or -1 if out_cap was too small. */
int64_t ww_run(WW *s, int64_t n, const int64_t *probes, int64_t np,
               const uint8_t *probe_map, int64_t *out, int64_t out_cap, int64_t t0) {
    int64_t w = s->w, h = s->h, written = 0;
    for (int64_t t = 0; t < n; t++) {
        int64_t ntouch = 0;
        if (grow(s, s->nh + 16)) return -2;
        for (int64_t k = 0; k < s->nh; k++) {
            int64_t i = s->heads[k];
            int64_t x = i % w, y = i / w;
            for (int dy = -1; dy <= 1; dy++) {
                int64_t yy = y + dy;
                if (yy < 0 || yy >= h) continue;
                for (int dx = -1; dx <= 1; dx++) {
                    if (!dx && !dy) continue;
                    int64_t xx = x + dx;
                    if (xx < 0 || xx >= w) continue;
                    int64_t j = yy * w + xx;
                    if (s->g[j] == 3) {
                        if (s->cnt[j]++ == 0) s->touch[ntouch++] = j;
                    }
                }
            }
        }
        int64_t nnew = 0;
        for (int64_t k = 0; k < ntouch; k++) {
            int64_t j = s->touch[k];
            uint8_t c = s->cnt[j];
            s->cnt[j] = 0;
            if (c == 1 || c == 2) s->nheads[nnew++] = j;
        }
        for (int64_t k = 0; k < s->nt; k++) s->g[s->tails[k]] = 3;
        for (int64_t k = 0; k < s->nh; k++) s->g[s->heads[k]] = 2;
        for (int64_t k = 0; k < nnew; k++) s->g[s->nheads[k]] = 1;
        /* tails <- heads, heads <- new heads */
        int64_t *tmp = s->tails; s->tails = s->heads; s->nt = s->nh;
        s->heads = tmp;
        if (grow(s, nnew + 16)) return -2;
        memcpy(s->heads, s->nheads, nnew * sizeof(int64_t));
        s->nh = nnew;
        if (np) {
            for (int64_t k = 0; k < nnew; k++) {
                int64_t j = s->heads[k];
                if (!probe_map[j]) continue;
                for (int64_t p = 0; p < np; p++) {
                    if (probes[p] == j) {
                        if (written + 2 > out_cap) return -1;
                        out[written++] = t0 + t + 1;
                        out[written++] = p;
                    }
                }
            }
        }
    }
    return written / 2;
}

int64_t ww_electrons(WW *s) { return s->nh + s->nt; }

void ww_state(WW *s, uint8_t *dst) { memcpy(dst, s->g, (size_t)(s->w * s->h)); }
