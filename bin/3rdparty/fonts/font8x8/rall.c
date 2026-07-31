#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

#include "font8x8_basic.h"
#include "font8x8_block.h"
#include "font8x8_box.h"
#include "font8x8_control.h"
#include "font8x8_ext_latin.h"
#include "font8x8_greek.h"
#include "font8x8_hiragana.h"
#include "font8x8_misc.h"
#include "font8x8_sga.h"

typedef struct {
    char *name;
    void *array;  /* Generic pointer to font data */
    int size;
} FontInfo;

FontInfo fonts[] = {
    {"basic",     (void*)font8x8_basic,      128},
    {"block",     (void*)font8x8_block,       32},
    {"box",       (void*)font8x8_box,        128},
    {"control",   (void*)font8x8_control,     32},
    {"ext_latin", (void*)font8x8_ext_latin,   96},
    {"greek",     (void*)font8x8_greek,       58},
    {"hiragana",  (void*)font8x8_hiragana,    96},
    {"misc",      (void*)font8x8_misc,         10},
    {"sga",       (void*)font8x8_sga,          26}
};

void render(char *bitmap) {
    int x, y;
    int set;
    for (x = 0; x < 8; x++) {
        for (y = 0; y < 8; y++) {
            set = bitmap[x] & (1 << y);
            printf("%c", set ? 'X' : ' ');
        }
        printf("\n");
    }
}

void usage(char *exec) {
    unsigned int i;
    printf("Usage: %s <font_name>\n\n", exec);
    printf("Available fonts:\n");
    for (i = 0; i < sizeof(fonts) / sizeof(fonts[0]); i++) {
        printf("  %-12s - %d characters\n", fonts[i].name, fonts[i].size);
    }
}

int main(int argc, char **argv) {
    unsigned int i, j;
    char *font_array;
    unsigned int font_size;
    
    if (argc != 2) {
        usage(argv[0]);
        return 1;
    }
    
    /* Find the requested font */
    for (i = 0; i < sizeof(fonts) / sizeof(fonts[0]); i++) {
        if (strcmp(argv[1], fonts[i].name) == 0) {
            font_array = fonts[i].array;
            font_size = fonts[i].size;
            break;
        }
    }
    
    if (i >= sizeof(fonts) / sizeof(fonts[0])) {
        fprintf(stderr, "Error: Unknown font '%s'\n\n", argv[1]);
        usage(argv[0]);
        return 2;
    }
    
    printf("Font: %s (%d characters)\n", fonts[i].name, font_size);
    printf("Size: %d characters\n\n", font_size);
    printf("Displaying all characters:\n");
    printf("==========================\n\n");
    
    /* Display all characters in the selected font */
    for (j = 0; j < font_size; j++) {
        printf("\nCharacter %d (U+%04X):\n", j, j);
        render(&font_array[j * 8]);
        
        if ((j > 0 && j % 16 == 15)) {
            /*
		printf("\n--- Press Enter to continue ---");
            getchar();
*/
        }
    }
    
    return 0;
}
