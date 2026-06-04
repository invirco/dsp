<?xml version='1.0'?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:template match ="/">
    <HTML xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <BODY>
      <xsl:apply-templates select="DOCUMENT"/>
    </BODY>
    </HTML>
  </xsl:template>

  <xsl:key name="REFERENCE-id" match="REFERENCE" use="concat('REFERENCE::', ../@id, @symbol)"/>

  <xsl:template match="DOCUMENT">
    <xsl:apply-templates select="LINKPROJECT"/>
  </xsl:template>

  <xsl:template match="LINKPROJECT">
    <H1>
      X-Ref for project 
      <A><xsl:attribute name="name">#<xsl:value-of select="@id"/></xsl:attribute></A>
      <I><xsl:value-of select="@name"/></I>
    </H1>
    <HR size="4" noshade="1"/>
    <xsl:apply-templates select="SECTION"/>
    <xsl:apply-templates select="OBJECT"/>

    <xsl:variable name="pid" select="@id"/>
    <xsl:variable name="iid" select="@importer_id"/>

    <xsl:for-each select="/DOCUMENT/LINKPROJECT_UNNEEDED_OBJECTS[@project_id=$pid]">
      <xsl:for-each select="OBJECT">
        <H2>
          <A><xsl:attribute name="name">#<xsl:value-of select="@id"/></xsl:attribute></A>
          UNNEEDED Object <xsl:value-of select="@name"/>
          from section <I><xsl:value-of select="@section"/></I>
        </H2>
        <xsl:if test="SYMBOL"><H3>Symbols</H3><xsl:apply-templates select="SYMBOL"/></xsl:if>
        <xsl:if test="REFERENCE">
          <H3>References</H3>
          <xsl:apply-templates select="REFERENCE[generate-id(.) = 
                                       generate-id(key('REFERENCE-id', concat('REFERENCE::', ../@id, @symbol))[1])]"/>
        </xsl:if>
        <HR size="2" noshade="1"/>
      </xsl:for-each>
    </xsl:for-each>

    <xsl:for-each select="/DOCUMENT/LINKPROJECT/IMPORTED_FILE[@importer=$iid]">
      <xsl:sort select="@name" order="ascending"/>
      <xsl:variable name="fid" select="@id"/>
      <xsl:if test="not($fid=preceding::IMPORTED_FILE/@id)">
        <H2>Input file <I><xsl:value-of select="@name"/></I></H2>
        <xsl:if test="not($fid=following::IMPORTED_FILE/@id)">
          (single instance)
        </xsl:if>
        <xsl:if test="$fid=following::IMPORTED_FILE/@id">
          Instantiated for:
          <LI>
            <A>
              <xsl:attribute name="href">#<xsl:value-of select="../@id"/></xsl:attribute>
              <xsl:value-of select="../@name"/>
            </A>
          </LI>
        </xsl:if>
      </xsl:if>
      <xsl:if test="$fid=preceding::IMPORTED_FILE/@id">
        <LI>
          <A>
            <xsl:attribute name="href">#<xsl:value-of select="../@id"/></xsl:attribute>
            <xsl:value-of select="../@name"/>
          </A>
        </LI>
      </xsl:if>
      <br/>
    </xsl:for-each>

  </xsl:template> 

  <xsl:template match="SECTION">
    <H2>
      Section
      <A><xsl:attribute name="name">#<xsl:value-of select="@id"/></xsl:attribute></A>
      <I><xsl:value-of select="@name"/></I>
      <small> [in <xsl:value-of select="parent::*/attribute::name"/>]</small>
    </H2>
    <xsl:if test="SYMBOL"><H3>Symbols</H3><xsl:apply-templates select="SYMBOL"/></xsl:if>

    <xsl:if test="REFERENCE">
      <H3>References</H3>
      <xsl:apply-templates select="REFERENCE[generate-id(.) = 
                                   generate-id(key('REFERENCE-id', concat('REFERENCE::', ../@id, @symbol))[1])]"/>
    </xsl:if>

    <HR size="2" noshade="1"/>
  </xsl:template>

  <xsl:template match="OBJECT">
    <H2>
      <A><xsl:attribute name="name">#<xsl:value-of select="@id"/></xsl:attribute></A>
      Object <xsl:value-of select="@name"/>
      from section <I><xsl:value-of select="@section"/></I>
      <small> [in <xsl:value-of select="parent::*/attribute::name"/>]</small>
    </H2>
    <xsl:if test="SYMBOL"><H3>Symbols</H3><xsl:apply-templates select="SYMBOL"/></xsl:if>

    <xsl:if test="REFERENCE">
      <H3>References</H3>
      <xsl:apply-templates select="REFERENCE[generate-id(.) = 
                                   generate-id(key('REFERENCE-id', concat('REFERENCE::', ../@id, @symbol))[1])]"/>
    </xsl:if>

    <HR size="2" noshade="1"/>
  </xsl:template>

  <xsl:template match="SYMBOL">
    <xsl:variable name="sid" select="@id"/>

    <A><xsl:attribute name="name">#<xsl:value-of select="@id"/></xsl:attribute></A>
    <xsl:value-of select="@name"/>

    <UL>
      <xsl:for-each select="/DOCUMENT/LINKPROJECT/SECTION/REFERENCE[@symbol_id=$sid]">
        <LI>Referenced by section
          <A>
            <xsl:attribute name="href">#<xsl:value-of select="../@id"/></xsl:attribute>
            <xsl:value-of select="../@name"/>
          </A>
        </LI>
      </xsl:for-each>

      <xsl:for-each select="/DOCUMENT/LINKPROJECT/OBJECT/REFERENCE[@symbol_id=$sid]">
        <LI>Referenced by object 
          <A>
            <xsl:attribute name="href">#<xsl:value-of select="../@id"/></xsl:attribute>
            <xsl:value-of select="../@name"/>
          </A>
          from section <I><xsl:value-of select="../@section"/></I>
        </LI>
      </xsl:for-each>

      <xsl:for-each select="/DOCUMENT/LINKPROJECT_UNNEEDED_OBJECTS/OBJECT/REFERENCE[@symbol_id=$sid]">
        <LI>Referenced by unneeded object 
          <A>
            <xsl:attribute name="href">#<xsl:value-of select="../@id"/></xsl:attribute>
            <xsl:value-of select="../@name"/>
          </A>
          from section <I><xsl:value-of select="../@section"/></I>
        </LI>
      </xsl:for-each>
     </UL>
  </xsl:template>

  <xsl:template match="REFERENCE">
    <A>
      <xsl:attribute name="href">#<xsl:value-of select="@symbol_id"/></xsl:attribute>
      <xsl:value-of select="@symbol"/>
    </A>
    <BR/>
  </xsl:template>

</xsl:stylesheet>