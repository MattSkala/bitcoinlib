# -*- coding: utf-8 -*-
#
#    BitcoinLib - Python Cryptocurrency Library
#    MNEMONIC class for BIP0039 Mnemonic Key management
#    © 2017 May - 1200 Web Development <http://1200wd.com/>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import hashlib
import hmac
from pbkdf2 import PBKDF2

from bitcoinlib.encoding import change_base, normalize_string, to_bytes

PBKDF2_ROUNDS = 2048
DEFAULT_LANGUAGE = 'english'
WORDLIST_DIR = os.path.join(os.path.dirname(__file__), 'wordlist')


class Mnemonic:
    """
    Class to convert, generate and parse Mnemonic sentences
    
    Implementation of BIP0039 for Mnemonics passphrases 

    Took some parts from Pavol Rusnak Trezors implementation, see https://github.com/trezor/python-mnemonic
    """

    def __init__(self, language=DEFAULT_LANGUAGE):
        """
        Init Mnemonic class and read wordlist of specified language
        
        :param language: use specific wordlist, i.e. chinese, dutch (in development), english, french, italian, japanese or spanish. Leave empty for default 'english'
        :type language: str
        
        """
        self._wordlist = []
        with open('%s/%s.txt' % (WORDLIST_DIR, language), 'r') as f:
            self._wordlist = [w.strip() for w in f.readlines()]

    @staticmethod
    def checksum(data):
        """
        Calculates checksum for given data key

        :param data: key string
        :type data: bytes, hexstring
        
        :return str: Checksum of key in bits
        """
        data = to_bytes(data)
        if len(data) % 4 > 0:
            raise ValueError('Data length in bits should be divisible by 32, but it is not (%d bytes = %d bits).' %
                             (len(data), len(data) * 8))
        hash = hashlib.sha256(data).digest()
        return change_base(hash, 256, 2, 256)[:len(data) * 8 // 32]

    def to_seed(self, words, passphrase=''):
        """
        Use Mnemonic words and passphrase to create a PBKDF2 seed (Password-Based Key Derivation Function 2)
        
        First use 'sanitize_mnemonic' to determine language and validate and check words

        :param words: Mnemonic passphrase as string with space seperated words
        :type words: str
        :param passphrase: A password to protect key, leave empty to disable
        :type passphrase: str
        
        :return bytes: PBKDF2 seed
        """
        words = self.sanitize_mnemonic(words)
        mnemonic = normalize_string(words)
        passphrase = passphrase.encode()
        return PBKDF2(mnemonic, b'mnemonic' + passphrase,
                      iterations=PBKDF2_ROUNDS,
                      macmodule=hmac,
                      digestmodule=hashlib.sha512).read(64)

    def word(self, index):
        """
        Get word from wordlist
        
        :param index: word index ID
        :type index: int
        
        :return str: A word from the dictionary 
        """
        return self._wordlist[index]

    def wordlist(self):
        """
        Get full selected wordlist. A wordlist is selected when initializing Mnemonic class
        
        :return list: Full list with 2048 words 
        """
        return self._wordlist

    def generate(self, strength=128, add_checksum=True):
        """
        Generate a random Mnemonic key
        
        Uses cryptographically secure os.urandom() function to generate data. Then creates a Mnemonic sentence with
        the 'to_mnemonic' method.

        :param strength: Key strenght in number of bits, default is 128 bits. It adviced to specify 128 bits or more, i.e.: 128, 256, 512 or 1024
        :type strength: int
        :param add_checksum: Included a checksum? Default is True
        :type add_checksum: bool
        
        :return str: Mnemonic passphrase consisting of a space seperated list of words
        """
        if strength % 32 > 0:
            raise ValueError("Strenght should be divisible by 32")
        data = os.urandom(strength // 8)
        return self.to_mnemonic(data, add_checksum=add_checksum)

    def to_mnemonic(self, data, add_checksum=True):
        """
        Convert key data entropy to Mnemonic sentence
        
        :param data: Key data entropy
        :type data: bytes, hexstring
        :param add_checksum: Included a checksum? Default is True
        :type add_checksum: bool
        
        :return str: Mnemonic passphrase consisting of a space seperated list of words
        """
        data = to_bytes(data)
        if add_checksum:
            binresult = change_base(data, 256, 2, len(data) * 8) + self.checksum(data)
            wi = change_base(binresult, 2, 2048)
        else:
            wi = change_base(data, 256, 2048)
        return normalize_string(' '.join([self._wordlist[i] for i in wi]))

    def to_entropy(self, words, includes_checksum=True):
        """
        Convert Mnemonic words back to key data entrophy

        :param words: Mnemonic words as string of list of words
        :type words: str
        :param includes_checksum: Boolean to specify if checksum is used. Default is True
        :type includes_checksum: bool
        
        :return bytes: Entrophy seed
        """
        words = self.sanitize_mnemonic(words)
        if isinstance(words, (str, unicode if sys.version < '3' else str)):
            words = words.split(' ')
        wi = []
        for word in words:
            wi.append(self._wordlist.index(word))
        ent = change_base(wi, 2048, 256, output_even=0)
        if includes_checksum:
            binresult = change_base(ent, 256, 2, len(ent) * 4)
            ent = change_base(binresult[:-len(binresult) // 33], 2, 256)

            # Check checksum
            checksum = binresult[-len(binresult) // 33:]
            if checksum != self.checksum(ent):
                raise Warning("Invalid checksum %s for entropy %s" % (checksum, ent))

        return ent

    @staticmethod
    def detect_language(words):
        """
        Detect language of given phrase
        
        :param words: List of space seperated words
        :type words: str
        
        :return str: Language 
        """
        words = normalize_string(words)
        if isinstance(words, (str, unicode if sys.version < '3' else bytes)):
            words = words.split(' ')

        wlcount = {}
        for fn in os.listdir(WORDLIST_DIR):
            if fn.endswith(".txt"):
                with open('%s/%s' % (WORDLIST_DIR, fn), 'r') as f:
                    wordlist = [w.strip() for w in f.readlines()]
                    language = fn.split('.')[0]
                    wlcount[language] = 0
                    for word in words:
                        if sys.version < '3':
                            word = word.encode('utf-8')
                        if word in wordlist:
                            wlcount[language] += 1
        detlang = max(wlcount.keys(), key=(lambda key: wlcount[key]))
        if not wlcount[detlang]:
            raise Warning("Could not detect language of Mnemonic sentence %s" % words)
        return detlang

    def sanitize_mnemonic(self, words):
        """
        Check and convert list of words to utf-8 encoding.
        
        Raises an error if unrecognised word is found
        
        :param words: List of space seperated words
        :type words: str
        
        :return str: Sanitized list of words
        """
        words = normalize_string(words)
        language = self.detect_language(words)
        if isinstance(words, (str, unicode if sys.version < '3' else bytes)):
            words = words.split(' ')
        with open('%s/%s.txt' % (WORDLIST_DIR, language), 'r') as f:
            wordlist = [w.strip() for w in f.readlines()]
            for word in words:
                if sys.version < '3':
                    word = word.encode('utf-8')
                if word not in wordlist:
                    raise Warning("Unrecognised word %s in mnemonic sentence" % word.encode('utf8'))
        return ' '.join(words)


if __name__ == '__main__':
    #
    # SOME EXAMPLES
    #

    from bitcoinlib.keys import HDKey
    from bitcoinlib.encoding import to_hexstring

    # Convert hexadecimal to mnemonic and back again to hex
    print("\nConvert hexadecimal to mnemonic and back again to hex")
    pk = '7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f'
    words = Mnemonic().to_mnemonic(pk)
    print("Hex                %s" % pk)
    print("Checksum bin       %s" % Mnemonic().checksum(pk))
    print("Mnemonic           %s" % words)
    print("Seed for HD Key    %s" % to_hexstring(Mnemonic().to_seed(words, 'test')))
    print("Back to Entropy    %s" % to_hexstring(Mnemonic().to_entropy(words)))

    # Generate a random Mnemonic HD Key
    print("\nGenerate a random Mnemonic HD Key")
    entsize = 128
    words = Mnemonic('english').generate(entsize)
    print("Your Mnemonic is   %s" % words)
    print("  (An avarage of %d tries is needed to brute-force this password)" % ((2 ** entsize) // 2))
    seed = Mnemonic().to_seed(words)
    hdk = HDKey().from_seed(seed)
    print("Seed for HD Key    %s" % to_hexstring(seed))
    print("HD Key WIF is      %s" % hdk.wif())

    # Generate a key from a Mnemonic sentence
    print("\nGenerate a key from a Mnemonic sentence")
    words = "type fossil omit food supply enlist move perfect direct grape clean diamond"
    print("Your Mnemonic is   %s" % words)
    seed = Mnemonic().to_seed(words)
    hdk = HDKey().from_seed(seed)
    print("Seed for HD Key    %s" % to_hexstring(seed))
    print("HD Key WIF is      %s" % hdk.wif())

    # Let's talk Spanish
    print("\nGenerate a key from a Spanish Mnemonic sentence")
    words = "laguna afirmar talón resto peldaño deuda guerra dorado catorce avance oasis barniz"
    print("Your Mnemonic is   %s" % words)
    seed = Mnemonic().to_seed(words)
    hdk = HDKey().from_seed(seed)
    print("Seed for HD Key    %s" % to_hexstring(seed))
    print("HD Key WIF is      %s" % hdk.wif())

    # Want some Chinese?
    print("\nGenerate a key from a Chinese Mnemonic sentence")
    words = "信 收 曉 捐 炭 祖 瘋 原 強 則 岩 蓄"
    print("Your Mnemonic is   %s" % words)
    seed = Mnemonic().to_seed(words)
    hdk = HDKey().from_seed(seed)
    print("Seed for HD Key    %s" % to_hexstring(seed))
    print("HD Key WIF is      %s" % hdk.wif())

    # Spanish Unicode mnemonic sentence
    print("\nGenerate a key from a Spanish UNICODE Mnemonic sentence")
    words = u"guion cruz envío papel otoño percha hazaña salir joya gorra íntimo actriz"
    print("Your Mnemonic is   %s" % words)
    seed = Mnemonic().to_seed(words, '1200 web development')
    hdk = HDKey().from_seed(seed)
    print("Seed for HD Key    %s" % to_hexstring(seed))
    print("HD Key WIF is      %s" % hdk.wif())

    # And Japanese
    print("\nGenerate a key from a Japanese UNICODE Mnemonic sentence")
    words = "あじわう　ちしき　たわむれる　おくさま　しゃそう　うんこう　ひてい　みほん　たいほ　てのひら　りこう　わかれる　かいすいよく　こもん　ねもと"
    print("Your Mnemonic is   %s" % words)
    seed = Mnemonic().to_seed(words, '1200 web development')
    hdk = HDKey().from_seed(seed)
    print("Seed for HD Key    %s" % to_hexstring(seed))
    print("HD Key WIF is      %s" % hdk.wif())

    # And Japanese
    # --- not supported at the moment ---
    # print("\nGenerate a key from a Japanese UNICODE Mnemonic sentence")
    # words = "あじわう　ちしき　たわむれる　おくさま　しゃそう　うんこう　ひてい　みほん　たいほ　てのひら　りこう　わかれる　かいすいよく　" \
    #         "こもん　ねもと"
    # print("Your Mnemonic is   %s" % words)
    # seed = change_base(Mnemonic().to_seed(words, '1200 web development'), 256, 16)
    # hdk = HDKey().from_seed(seed)
    # print("Seed for HD Key    %s" % change_base(seed, 256, 16))
    # print("HD Key WIF is      %s" % hdk)
    # print("HD Key WIF <==>    xprv9s21ZrQH143K2dq9wumtjiDMnMqF56xswR5ZQDpQehp34zNtAEHCADTDt6RAEpxtsEwQbissfq2p4Hq9"
    #       "NY6Fbf7F5pRKkddcXoTsu5xWziU")

    # Japanese Json test
    # [
    #     "",
    #     "あじわう　ちしき　たわむれる　おくさま　しゃそう　うんこう　ひてい　みほん　たいほ　てのひら　りこう　わかれる　かいすいよく　こもん　"
    #     "ねもと",
    #     "6e0404f30a518af203d70ebc0b5839c04e70d671699ffaad9f0447592b59b68afae9d938db1834c0d1aeac3554212dfedf3c42f5a"
    #     "fd60740a308589518174e10",
    #     "xprv9s21ZrQH143K2dq9wumtjiDMnMqF56xswR5ZQDpQehp34zNtAEHCADTDt6RAEpxtsEwQbissfq2p4Hq9NY6Fbf7F5pRKkddcXoTsu"
    #     "5xWziU",
    #     "1200 web development"
    # ]
