/*********************************************************************
 *
 * Copyright (C) 2007,  Simon Kagstrom
 *
 * Filename:      elf.hh
 * Author:        Simon Kagstrom <simon.kagstrom@gmail.com>
 * Description:   ELF stuff
 *
 * $Id:$
 *
 ********************************************************************/
#ifndef __ELF_HH__
#define __ELF_HH__

#include <stdint.h>
#include <stdlib.h>

#include <libelf.h>
#include <ght_hash_table.h>

class CibylElf;

class ElfSymbol
{
public:
  ElfSymbol(int index, uint32_t addr, uint32_t size, int type, const char *name)
  {
    this->index = index;
    this->addr = addr;
    this->size = size;
    this->type = type;
    this->name = name;
  }

  int index;
  uint32_t addr;
  uint32_t size;
  int type;
  const char *name;
};


class ElfReloc
{
public:
  ElfReloc(uint32_t addr, int type, ElfSymbol *sym)
  {
    this->addr = addr;
    this->type = type;
    this->sym = sym;
  }

  uint32_t addr;
  int type;
  ElfSymbol *sym;
};


class CibylElf
{
public:
  static CibylElf *getInstance();

  CibylElf(const char *filname);

  ElfSymbol **getSymbolsByType(char type);

  ElfSymbol **getFunctions();

  int getNumberOfFunctions();

  ElfReloc **getRelocations();

  int getNumberOfRelocations();

  uint32_t getEntryPoint() { return this->entryPoint; }

  uint8_t *getText() { return this->text; };

  uint8_t *getData() { return this->data; };

  uint8_t *getRodata() { return this->rodata; };

  uint8_t *getCtors() { return this->ctors; };

  uint8_t *getDtors() { return this->dtors; };

  size_t getTextSize() { return this->textSize; };

  size_t getDataSize() { return this->dataSize; };

  size_t getRodataSize() { return this->rodataSize; };

  size_t getCtorsSize() { return this->ctorsSize; };

  size_t getDtorsSize() { return this->dtorsSize; };

  size_t getCibylStrtabSize() { return this->cibylstrtabSize; };

  char *getCibylStrtabString(uint32_t offset)
  {
    return ((char*)this->cibylstrtab) + offset;
  }

private:
  void handleSymtab(Elf_Scn *scn);
  void fixupSymbolSize(ElfSymbol **table, int n);

  static CibylElf *instance;

  Elf *elf; /* from libelf */

  ElfSymbol **symbols;
  ElfSymbol **functionSymbols;
  ElfSymbol **dataSymbols;

  uint8_t *text;
  uint8_t *data;
  uint8_t *rodata;
  uint8_t *ctors;
  uint8_t *dtors;
  uint8_t *cibylstrtab;

  int n_symbols;
  int n_functionSymbols;
  int n_dataSymbols;
  ght_hash_table_t *symtable;

  ElfReloc **relocs;
  int n_relocs;

  size_t textSize, dataSize, rodataSize, ctorsSize, dtorsSize, cibylstrtabSize;

  uint32_t entryPoint;
};

#endif /* !__ELF_HH__ */
