<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:template match ="/">
    <HTML xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <BODY>
      <xsl:apply-templates select="DOCUMENT"/>
    </BODY>
    </HTML>
  </xsl:template>

  <xsl:template match="DOCUMENT">
    <xsl:if test="count(LINKPROJECT) > 1">
      <xsl:for-each select="LINKPROJECT">
        <A>
          <xsl:attribute name="href">#<xsl:value-of select="@id"/></xsl:attribute>
          Memory map of <xsl:value-of select="@name"/>
        </A>
        <BR/>
      </xsl:for-each>
    <P/><HR size="16" noshade="1"/>
    </xsl:if>
    <xsl:apply-templates select="*"/>
  </xsl:template>

  <xsl:template match="LINKPROJECT">
    <H1>
      Memory map of link project 
      <A><xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute></A>
      <I><xsl:value-of select="@name"/></I>
    </H1>
    <xsl:variable name="hasType" select="MEMORY[not(@type='')]"/>
    <TABLE border="1" width="100%" cellpadding="0" cellspacing="0">
    <THEAD bgcolor="#006fff">
      <TR>
        <TH>Memory</TH>
        <TH>Start address</TH>
        <TH>End address</TH>
        <xsl:if test="$hasType"><TH colwidth="0%">Type</TH></xsl:if>
        <TH>Qualifier</TH>
        <TH>Width</TH>
        <TH>Used words[1]</TH>
        <TH>Unused words</TH>
      </TR>
    </THEAD>
    <TBODY bgolor="#88ccff">
    <xsl:for-each select="MEMORY">
      <TR>
        <TD>
          <A>
            <xsl:attribute name="href">#<xsl:value-of select="@id"/></xsl:attribute>
            <xsl:value-of select="@name"/>
          </A>
        </TD>
        <TD align="right"><xsl:value-of select="@start_address"/></TD>
        <TD align="right"><xsl:value-of select="@end_address"/></TD>
        <xsl:if test="$hasType"><TD align="right"><xsl:value-of select="@type"/></TD></xsl:if>
        <TD align="right"><xsl:value-of select="@qualifier"/></TD>
        <TD align="right"><xsl:value-of select="@width"/></TD>
        <TD align="right"><xsl:value-of select="@words_used"/></TD>
        <TD align="right"><xsl:value-of select="@words_unused"/></TD>
      </TR>
    </xsl:for-each> 
    </TBODY>
    </TABLE>
    <xsl:text>Note [1]: Padding bytes for alignment gaps are not counted towards used words.</xsl:text>
    <P/><HR size="6" noshade="1"/>
    <xsl:apply-templates select="LDF_SYMBOLS"/>
    <xsl:apply-templates select="MEMORY"/>
  </xsl:template> 

  <xsl:template match="OVERLAYLINKPROJECT">
    <H1>
      Overlay <I><xsl:value-of select="FILE_NAME"/></I>
    </H1>
    <xsl:apply-templates select="OUTPUT_SECTIONS"/>
  </xsl:template>

  <xsl:template match="LDF_SYMBOLS">
    <H2>
      LDF symbols <I><xsl:value-of select="@name"/></I>
    </H2>
    <TABLE border="1">
    <THEAD><TR><TH>Symbol</TH><TH>Address</TH></TR></THEAD>
    <xsl:for-each select="SYMBOL">
      <TR>
        <TD><xsl:value-of select="@name"/></TD>
        <TD align="right"><xsl:value-of select="@address"/></TD>
      </TR>
    </xsl:for-each>
    </TABLE>
    <P/><HR size="3" noshade="1"/>
  </xsl:template> 

  <xsl:template match="MEMORY">
    <H2>
      <A><xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute></A>
      Memory <I><xsl:value-of select="@name"/></I>
    </H2>
    <xsl:apply-templates select="OUTPUT_SECTIONS"/>
  </xsl:template> 

  <xsl:template match="OUTPUT_SECTIONS">
    <xsl:variable name="hasMemType" select="OUTPUT_SECTION[@memory_type]"/>
    <TABLE border="1">
    <THEAD>
      <TR>
        <TH>Output section</TH>
        <TH>Type</TH>
        <xsl:if test="$hasMemType">
          <TH>Memory type</TH>
          <TH>Memory width</TH>
        </xsl:if>
        <TH>Start address</TH>
        <TH>Size in words</TH>
        <xsl:if test="OUTPUT_SECTION[@word_size_reserved != '0x0']">
          <TH>Reserved size in words</TH>
        </xsl:if>
      </TR>
    </THEAD>
    <xsl:for-each select="OUTPUT_SECTION">
      <TR>
        <TD>
          <xsl:choose>
            <xsl:when test="INPUT_SECTIONS">
              <A>
                <xsl:attribute name="href">#<xsl:value-of select="@id"/></xsl:attribute>
                <xsl:value-of select="@name"/>
              </A>
            </xsl:when>
            <xsl:otherwise>
              <xsl:value-of select="@name"/>
            </xsl:otherwise>
          </xsl:choose>
        </TD>
        <TD align="right"><xsl:value-of select="@type"/></TD>
        <xsl:if test="$hasMemType">
          <TD align="right"><xsl:value-of select="@memory_type"/></TD>
          <TD align="right"><xsl:value-of select="@memory_width"/></TD>
        </xsl:if>
        <TD align="right"><xsl:value-of select="@start_address"/></TD>
        <TD align="right"><xsl:value-of select="@word_size"/></TD>
        <xsl:if test="../OUTPUT_SECTION[@word_size_reserved != '0x0']">
          <TD align="right"><xsl:value-of select="@word_size_reserved"/></TD>
        </xsl:if>
      </TR>
    </xsl:for-each> 
    </TABLE>
    <P/><HR size="3" noshade="1"/>
    <xsl:if test="OUTPUT_SECTION[INPUT_SECTIONS]">
    <xsl:apply-templates select="OUTPUT_SECTION"/>
    </xsl:if>
  </xsl:template> 

  <xsl:template match="OUTPUT_SECTION">
    <H3>
      <A><xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute></A>
      Output section <I><xsl:value-of select="@name"/></I>
    </H3>
    <TABLE border="1">
    <THEAD>
      <TR>
        <TH>Input section</TH>
        <TH>Start address</TH>
        <TH>Size</TH>
        <TH>Input file</TH>
      </TR>
    </THEAD>
    <xsl:for-each select="INPUT_SECTIONS/INPUT_SECTION">
      <TR>
        <TD>
          <A>
            <xsl:attribute name="href">#<xsl:value-of select="@id"/></xsl:attribute>
            <xsl:value-of select="@name"/>
          </A>
        </TD>
        <TD align="right"><xsl:value-of select="@start_address"/></TD>
        <TD align="right"><xsl:value-of select="@size"/></TD>
        <TD><xsl:value-of select="INPUT_FILE"/></TD>
      </TR>
    </xsl:for-each> 
    </TABLE>

    <xsl:for-each select="INPUT_SECTIONS/INPUT_SECTION">
      <H3>
        <A><xsl:attribute name="name"><xsl:value-of select="@id"/></xsl:attribute></A>
        Input section
        <I>
          <xsl:value-of select="INPUT_FILE"/>(<xsl:value-of select="@name"/>)
          <xsl:if test="@split">:<small><xsl:value-of select="@element_at"/></small></xsl:if>
          <xsl:if test="@abs_placed"><small> (absolutely placed) </small></xsl:if>
        </I>
      </H3>
      <TABLE border="1">
      <THEAD><TR><TH>Symbol</TH><TH>Demangled name</TH><TH>Address</TH><TH>Size</TH><TH>Binding</TH></TR></THEAD>
      <xsl:for-each select="SYMBOL">
        <xsl:if test="not(starts-with(@name, '.'))">
          <TR>
            <TD><xsl:value-of select="@name"/></TD>
            <TD align="left"><xsl:value-of select="DEMANGLED_NAME"/></TD>
            <TD align="right"><xsl:value-of select="@address"/></TD>
            <TD align="right"><xsl:value-of select="@size"/></TD>
            <TD align="right"><xsl:value-of select="@binding"/></TD>
          </TR>
        </xsl:if>
      </xsl:for-each>
      </TABLE>
    </xsl:for-each> 
    <P/><HR size="3" noshade="1"/>
  </xsl:template> 

</xsl:stylesheet>
