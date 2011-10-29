/****************************************************************************************
 *   Copyright: Copyright (C) 2009-2010 Ulrik Mikaelsson. All rights reserved
 *
 *   License:
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ***************************************************************************************/

module daemon.lib.stateless;

private import tango.io.device.File;

version (Posix) import tango.stdc.posix.unistd;

/*****************************************************************************************
 * Class for file with stateless read/write. I/E no need for the user to care about
 * read/write position.
 ****************************************************************************************/
class StatelessFile : File {
    /*************************************************************************************
     * Reads as many bytes as possible into dst, and returns the amount.
     ************************************************************************************/
    size_t pRead(ulong pos, void[] dst) {
        version (Posix) { // Posix has pread() for atomic seek+read
            ssize_t got = pread(fileHandle, dst.ptr, dst.length, pos);
            if (got is -1)
                error;
            else
               if (got is 0 && dst.length > 0)
                   return Eof;
            return got;
        } else synchronized (this) {
            seek(pos);
            return read(buf);
        }
    }

    /*************************************************************************************
     * Reads as many bytes as possible into buf, and returns the amount.
     ************************************************************************************/
    size_t pWrite(ulong pos, void[] src) {
        version (Posix) { // Posix has pwrite() for atomic write+seek
            ssize_t written = pwrite(fileHandle, src.ptr, src.length, pos);
            if (written is -1)
                error;
            return written;
        } else synchronized (this) {
            seek(pos);
            return write(data);
        }
    }
}